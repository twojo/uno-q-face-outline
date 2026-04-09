# SPDX-FileCopyrightText: Copyright (C) 2025 Wojo
#
# SPDX-License-Identifier: MIT

"""
On-device face detection via TFLite on the QRB2210 MPU.

This module provides FaceDetectorMPU, which wraps a TFLite face detection
model for native on-device inference. When a .tflite model is present in
python/models/, the detector runs face detection directly on the MPU
instead of relying on the browser's MediaPipe WASM engine.

Architecture:
  Camera (v4l2) → FaceDetectorMPU (TFLite) → face results
                                             ├→ Bridge → MCU (LED/RGB)
                                             └→ WebSocket → Browser (overlay)

Graceful degradation:
  - No .tflite model found  → skip, browser-only mode
  - No ai-edge-litert       → skip, browser-only mode
  - No camera device        → skip, browser-only mode
  - Model load failure      → skip with error log, browser-only mode

All failures are non-fatal. The system always falls back to browser-based
detection so the demo keeps working even without the AI Hub models.
"""

import os
import time
import json
import threading
from pathlib import Path

MODELS_DIR = Path(__file__).parent / "models"

_tflite_available = False
_tflite_backend = None
_Interpreter = None

try:
    from ai_edge_litert.interpreter import Interpreter
    _Interpreter = Interpreter
    _tflite_available = True
    _tflite_backend = "ai_edge_litert"
except ImportError:
    try:
        from tflite_runtime.interpreter import Interpreter
        _Interpreter = Interpreter
        _tflite_available = True
        _tflite_backend = "tflite_runtime"
    except ImportError:
        try:
            import tensorflow as tf
            _Interpreter = tf.lite.Interpreter
            _tflite_available = True
            _tflite_backend = "tensorflow"
        except (ImportError, AttributeError):
            pass

_numpy_available = False
_np = None
try:
    import numpy as np
    _np = np
    _numpy_available = True
except ImportError:
    pass

_cv2_available = False
_cv2 = None
try:
    import cv2
    _cv2 = cv2
    _cv2_available = True
except ImportError:
    pass


def find_models():
    models = {}
    if not MODELS_DIR.exists():
        return models
    for f in MODELS_DIR.glob("*.tflite"):
        size_kb = f.stat().st_size / 1024
        models[f.stem] = {
            "path": str(f),
            "size_kb": round(size_kb),
            "name": f.stem,
        }
    return models


def find_camera():
    for i in range(4):
        dev = f"/dev/video{i}"
        if os.path.exists(dev):
            return dev, i
    return None, None


class FaceDetectorMPU:
    def __init__(self, logger=None):
        self._logger = logger
        self._running = False
        self._thread = None
        self._interpreter = None
        self._model_path = None
        self._model_name = None
        self._camera_dev = None
        self._camera_idx = None
        self._cap = None
        self._lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()

        self._last_faces = []
        self._last_inference_ms = 0
        self._frame_count = 0
        self._detect_count = 0
        self._fps = 0.0

        self._on_faces_callback = None
        self._on_no_faces_callback = None

        self._available = False
        self._status = "not_initialized"
        self._status_detail = ""

    def _log(self, msg):
        if self._logger:
            self._logger.info(msg)

    def _log_error(self, msg):
        if self._logger:
            self._logger.error(msg)

    @property
    def available(self):
        return self._available

    @property
    def status(self):
        return self._status

    @property
    def status_detail(self):
        return self._status_detail

    @property
    def running(self):
        return self._running

    @property
    def fps(self):
        return self._fps

    @property
    def last_inference_ms(self):
        return self._last_inference_ms

    @property
    def frame_count(self):
        return self._frame_count

    @property
    def detect_count(self):
        return self._detect_count

    @property
    def last_faces(self):
        with self._lock:
            return list(self._last_faces)

    def on_faces(self, callback):
        self._on_faces_callback = callback

    def on_no_faces(self, callback):
        self._on_no_faces_callback = callback

    def initialize(self):
        self._log("[AI-HUB] Initializing on-device face detector...")

        if not _tflite_available:
            self._status = "no_runtime"
            self._status_detail = "TFLite runtime not installed (pip install ai-edge-litert)"
            self._log(f"[AI-HUB] ⚠ {self._status_detail}")
            return False

        if not _numpy_available:
            self._status = "no_numpy"
            self._status_detail = "numpy not installed (pip install numpy)"
            self._log(f"[AI-HUB] ⚠ {self._status_detail}")
            return False

        if not _cv2_available:
            self._status = "no_opencv"
            self._status_detail = "OpenCV not installed (pip install opencv-python-headless)"
            self._log(f"[AI-HUB] ⚠ {self._status_detail}")
            return False

        models = find_models()
        if not models:
            self._status = "no_model"
            self._status_detail = f"No .tflite models in {MODELS_DIR}"
            self._log(f"[AI-HUB] ⚠ {self._status_detail}")
            self._log("[AI-HUB]   Run: python ai_hub_setup.py --compile --model face_det_lite")
            return False

        preferred = ["face_det_lite", "mediapipe_face_detector", "mediapipe_face"]
        chosen = None
        for name in preferred:
            if name in models:
                chosen = models[name]
                break
        if not chosen:
            chosen = list(models.values())[0]

        self._model_path = chosen["path"]
        self._model_name = chosen["name"]
        self._log(f"[AI-HUB] Loading model: {self._model_name} ({chosen['size_kb']} KB)")

        try:
            self._interpreter = _Interpreter(model_path=self._model_path)
            self._interpreter.allocate_tensors()

            input_details = self._interpreter.get_input_details()
            output_details = self._interpreter.get_output_details()

            self._input_details = input_details
            self._output_details = output_details

            self._log(f"[AI-HUB] ✓ Model loaded — {len(input_details)} input(s), {len(output_details)} output(s)")
            for inp in input_details:
                self._log(f"[AI-HUB]   Input: shape={inp['shape']} dtype={inp['dtype']}")
            for out in output_details:
                self._log(f"[AI-HUB]   Output: shape={out['shape']} dtype={out['dtype']}")

            test_input = _np.zeros(input_details[0]['shape'], dtype=input_details[0]['dtype'])
            self._interpreter.set_tensor(input_details[0]['index'], test_input)
            t0 = time.time()
            self._interpreter.invoke()
            warmup_ms = (time.time() - t0) * 1000
            self._log(f"[AI-HUB] ✓ Warmup inference: {warmup_ms:.1f} ms")

        except Exception as e:
            self._status = "model_error"
            self._status_detail = f"Failed to load model: {e}"
            self._log_error(f"[AI-HUB] ✗ {self._status_detail}")
            return False

        cam_dev, cam_idx = find_camera()
        if cam_dev is None:
            self._status = "no_camera"
            self._status_detail = "No camera device found (/dev/video0-3)"
            self._log(f"[AI-HUB] ⚠ {self._status_detail}")
            self._log("[AI-HUB]   Model loaded but cannot capture frames without a camera")
            self._available = True
            return True

        self._camera_dev = cam_dev
        self._camera_idx = cam_idx
        self._log(f"[AI-HUB] ✓ Camera found: {cam_dev}")

        self._available = True
        self._status = "ready"
        self._status_detail = f"Model: {self._model_name}, Camera: {cam_dev}"
        self._log(f"[AI-HUB] ✓ Face detector ready — {self._status_detail}")
        return True

    def start(self):
        with self._lifecycle_lock:
            if not self._available:
                self._log("[AI-HUB] Cannot start — detector not available")
                return False

            if self._camera_idx is None:
                self._log("[AI-HUB] Cannot start capture — no camera device")
                return False

            if self._running:
                return True

            self._running = True
            self._thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._thread.start()
            self._log("[AI-HUB] ✓ Face detection capture loop started")
            return True

    def stop(self):
        with self._lifecycle_lock:
            self._running = False
            thread = self._thread
            self._thread = None

        if thread:
            thread.join(timeout=5)
        if self._cap:
            self._cap.release()
            self._cap = None
        self._log("[AI-HUB] Face detection stopped")

    def _capture_loop(self):
        try:
            self._cap = _cv2.VideoCapture(self._camera_idx)
            if not self._cap.isOpened():
                self._log_error(f"[AI-HUB] Failed to open camera {self._camera_idx}")
                self._running = False
                return

            self._cap.set(_cv2.CAP_PROP_FRAME_WIDTH, 640)
            self._cap.set(_cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self._cap.set(_cv2.CAP_PROP_FPS, 15)

            self._log(f"[AI-HUB] Camera opened: {int(self._cap.get(_cv2.CAP_PROP_FRAME_WIDTH))}x"
                       f"{int(self._cap.get(_cv2.CAP_PROP_FRAME_HEIGHT))} @ "
                       f"{int(self._cap.get(_cv2.CAP_PROP_FPS))} FPS")

            fps_counter = 0
            fps_time = time.time()

            while self._running:
                ret, frame = self._cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue

                self._frame_count += 1
                fps_counter += 1

                now = time.time()
                if now - fps_time >= 1.0:
                    self._fps = fps_counter / (now - fps_time)
                    fps_counter = 0
                    fps_time = now

                faces = self._run_inference(frame)

                with self._lock:
                    self._last_faces = faces

                if faces:
                    self._detect_count += 1
                    if self._on_faces_callback:
                        try:
                            self._on_faces_callback(faces)
                        except Exception as e:
                            self._log_error(f"[AI-HUB] Faces callback error: {e}")
                else:
                    if self._on_no_faces_callback:
                        try:
                            self._on_no_faces_callback()
                        except Exception as e:
                            self._log_error(f"[AI-HUB] No-faces callback error: {e}")

        except Exception as e:
            self._log_error(f"[AI-HUB] Capture loop error: {e}")
        finally:
            self._running = False
            if self._cap:
                self._cap.release()
                self._cap = None

    def _run_inference(self, frame):
        input_detail = self._input_details[0]
        target_shape = tuple(input_detail['shape'])
        ndim = len(target_shape)

        total_el = 1
        for d in target_shape:
            total_el *= d

        if ndim == 4:
            if target_shape[1] <= 4:
                h, w = target_shape[2], target_shape[3]
                resized = _cv2.resize(frame, (w, h))
                rgb = _cv2.cvtColor(resized, _cv2.COLOR_BGR2RGB)
                input_data = _np.transpose(rgb, (2, 0, 1))
                input_data = _np.expand_dims(input_data, axis=0)
            else:
                h, w = target_shape[1], target_shape[2]
                resized = _cv2.resize(frame, (w, h))
                rgb = _cv2.cvtColor(resized, _cv2.COLOR_BGR2RGB)
                input_data = _np.expand_dims(rgb, axis=0)
        elif ndim == 3:
            if target_shape[0] <= 4:
                h, w = target_shape[1], target_shape[2]
                resized = _cv2.resize(frame, (w, h))
                rgb = _cv2.cvtColor(resized, _cv2.COLOR_BGR2RGB)
                input_data = _np.transpose(rgb, (2, 0, 1))
            else:
                h, w = target_shape[0], target_shape[1]
                resized = _cv2.resize(frame, (w, h))
                rgb = _cv2.cvtColor(resized, _cv2.COLOR_BGR2RGB)
                input_data = rgb
        else:
            for ch_guess in [3, 1]:
                if total_el % ch_guess == 0:
                    pixels = total_el // ch_guess
                    side = int(pixels ** 0.5)
                    if side * side * ch_guess == total_el:
                        h, w = side, side
                        resized = _cv2.resize(frame, (w, h))
                        if ch_guess == 3:
                            input_data = _cv2.cvtColor(resized, _cv2.COLOR_BGR2RGB)
                        else:
                            input_data = _cv2.cvtColor(resized, _cv2.COLOR_BGR2GRAY)
                        break
            else:
                self._logger.warning(f"[FaceDetMPU] Unsupported input shape {target_shape} — skipping frame")
                return []

        input_data = input_data.astype(input_detail['dtype'])

        if input_detail['dtype'] == _np.float32:
            input_data = input_data / 255.0

        try:
            input_data = input_data.reshape(target_shape)
        except ValueError as e:
            self._logger.warning(f"[FaceDetMPU] Reshape failed {input_data.shape} → {target_shape}: {e}")
            return []

        self._interpreter.set_tensor(input_detail['index'], input_data)

        t0 = time.time()
        self._interpreter.invoke()
        self._last_inference_ms = (time.time() - t0) * 1000

        faces = []
        outputs = []
        for out_detail in self._output_details:
            outputs.append(self._interpreter.get_tensor(out_detail['index']))

        if len(outputs) >= 2:
            boxes = outputs[0]
            scores = outputs[1] if len(outputs) > 1 else None

            if scores is not None and len(scores.shape) >= 1:
                score_data = scores.flatten()
                box_data = boxes.reshape(-1, 4) if len(boxes.shape) >= 2 else boxes

                for i, score in enumerate(score_data):
                    if score > 0.5 and i < len(box_data):
                        box = box_data[i]
                        faces.append({
                            "box": [float(box[0]), float(box[1]),
                                    float(box[2]), float(box[3])],
                            "score": float(score),
                        })

                faces.sort(key=lambda f: f["score"], reverse=True)
                faces = faces[:4]

        elif len(outputs) == 1:
            raw = outputs[0].flatten()
            if len(raw) >= 5:
                faces.append({
                    "box": [float(raw[0]), float(raw[1]),
                            float(raw[2]), float(raw[3])],
                    "score": float(raw[4]) if len(raw) > 4 else 1.0,
                })

        return faces

    def get_status_dict(self):
        return {
            "available": self._available,
            "status": self._status,
            "detail": self._status_detail,
            "model": self._model_name,
            "running": self._running,
            "fps": round(self._fps, 1),
            "inference_ms": round(self._last_inference_ms, 1),
            "frame_count": self._frame_count,
            "detect_count": self._detect_count,
            "tflite_backend": _tflite_backend,
            "faces": len(self._last_faces),
        }
