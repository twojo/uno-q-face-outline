#!/usr/bin/env python3
#
# Wojo's Uno Q Face Outline Tracker Demo — Direct SSH Version
# Arduino Uno Q (Qualcomm QRB2210)
#
# Standalone face detection for the Uno Q's Cortex-A53 — no App Lab needed.
# SSH into your Uno Q and run:
#
#   ./setup.sh                        # one-time: installs deps + downloads models
#   python3 direct/face_tracker.py    # start tracking
#
# Uses OpenCV's YuNet face detector (75K params, 233 KB) for detection
# and optionally a 468-landmark face mesh model via ONNX Runtime for
# full mesh outlines. This is the same landmark count as MediaPipe's
# face mesh — we use a compatible ONNX model instead of MediaPipe's
# Python bindings because mediapipe lacks reliable ARM64 Linux wheels
# for the QRB2210's Cortex-A53.
#
# Pure Python — no App Lab, no Bridge, no MCU dependencies.

import cv2
import numpy as np
import time
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
MODELS_DIR = os.path.join(PROJECT_DIR, "models")

FACE_MODEL = os.path.join(MODELS_DIR, "face_detection_yunet.onnx")
MESH_MODEL = os.path.join(MODELS_DIR, "face_mesh_192x192.onnx")

CONFIDENCE = 0.5
CAMERA_INDEX = 0
FRAME_W, FRAME_H = 640, 480

HAS_MESH = False
mesh_session = None

try:
    import onnxruntime as ort
    if os.path.isfile(MESH_MODEL):
        mesh_session = ort.InferenceSession(MESH_MODEL, providers=["CPUExecutionProvider"])
        HAS_MESH = True
        print("[OK] Face mesh model loaded (468 landmarks via ONNX Runtime)")
        print("     Same landmark set as MediaPipe Face Mesh, ARM64-compatible")
    else:
        print("[INFO] Face mesh model not found — 468-landmark outlines disabled")
        print("       Fix: ./model_get.sh face-mesh")
        print("       Or:  ./setup.sh   (downloads all models)")
except ImportError:
    print("[INFO] onnxruntime not installed — 468-landmark face mesh disabled")
    print("       Fix: pip3 install onnxruntime")
    print("       Face detection still works (YuNet via OpenCV, no extra deps)")


def get_face_mesh(frame, bbox):
    if not HAS_MESH or mesh_session is None:
        return None

    x, y, w, h = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])

    pad = int(max(w, h) * 0.2)
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(frame.shape[1], x + w + pad)
    y2 = min(frame.shape[0], y + h + pad)

    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None

    inp = cv2.resize(crop, (192, 192))
    inp = inp.astype(np.float32) / 255.0
    inp = np.transpose(inp, (2, 0, 1))
    inp = np.expand_dims(inp, axis=0)

    crop_x1 = np.array([[x1]], dtype=np.int32)
    crop_y1 = np.array([[y1]], dtype=np.int32)
    crop_w = np.array([[x2 - x1]], dtype=np.int32)
    crop_h = np.array([[y2 - y1]], dtype=np.int32)

    try:
        outputs = mesh_session.run(None, {
            "input": inp,
            "crop_x1": crop_x1,
            "crop_y1": crop_y1,
            "crop_width": crop_w,
            "crop_height": crop_h,
        })
        score = outputs[0][0][0]
        landmarks = outputs[1][0]
        if score > 0.5:
            return landmarks
    except Exception:
        pass

    return None


def main():
    if not os.path.isfile(FACE_MODEL):
        print(f"ERROR: Face detection model not found at {FACE_MODEL}")
        print("")
        print("  Fix: Run the setup script to download models:")
        print("    cd " + PROJECT_DIR)
        print("    ./setup.sh")
        print("")
        print("  Or download just the face detector:")
        print("    ./model_get.sh face-detection")
        print("")
        print("  The YuNet model is only 233 KB and needs internet access.")
        print("  Check: curl -s https://github.com > /dev/null && echo 'OK' || echo 'No internet'")
        sys.exit(1)

    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)

    if not cap.isOpened():
        print("ERROR: Cannot open camera")
        print(f"       Tried /dev/video{CAMERA_INDEX}")
        print("")
        print("  Checklist:")
        print("    1. Is a USB webcam plugged into the Uno Q's USB hub?")
        print("    2. Run: ls /dev/video*    (should show /dev/video0)")
        print("    3. Try: v4l2-ctl --list-devices")
        print("    4. If using a USB-C multiport adapter, ensure it has power delivery")
        print("    5. Some webcams need USB 2.0 — try a different port on the hub")
        print("")
        print("  Note: The Uno Q has a single USB-C port. You need a powered USB hub")
        print("  or the Arduino USB-C multiport adapter to connect both power and camera.")
        sys.exit(1)

    detector = cv2.FaceDetectorYN_create(
        FACE_MODEL, "", (FRAME_W, FRAME_H),
        score_threshold=CONFIDENCE,
        nms_threshold=0.3,
        top_k=5000
    )

    face_present = False
    face_count = 0
    mesh_landmarks = 0

    print("")
    print("================================================")
    print("  Wojo's Face Tracker — Arduino Uno Q")
    print("  Qualcomm QRB2210 (Cortex-A53)")
    print("================================================")
    print(f"  Camera: {FRAME_W}x{FRAME_H} @ /dev/video{CAMERA_INDEX}")
    print(f"  Detector: YuNet ({os.path.getsize(FACE_MODEL) // 1024} KB)")
    print(f"  Mesh: {'468 landmarks (ONNX, MediaPipe-compatible)' if HAS_MESH else 'disabled (detection only)'}")
    print(f"  Confidence: {CONFIDENCE}")
    print("  Press Ctrl+C to stop")
    print("================================================")
    print("")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                continue

            h, w = frame.shape[:2]
            detector.setInputSize((w, h))
            _, faces = detector.detect(frame)

            n = faces.shape[0] if faces is not None else 0

            if n > 0 and not face_present:
                face_present = True
                face_count += 1

                if HAS_MESH and faces is not None:
                    landmarks = get_face_mesh(frame, faces[0][:4])
                    if landmarks is not None:
                        mesh_landmarks = len(landmarks)

                print(f"[FACE] Detected {n} face(s) — total: {face_count}"
                      + (f" — mesh: {mesh_landmarks} landmarks" if mesh_landmarks else ""))

            elif n == 0 and face_present:
                face_present = False
                mesh_landmarks = 0
                print("[FACE] Lost")

            time.sleep(0.033)

    except KeyboardInterrupt:
        print("\nStopping...")
        cap.release()
        print(f"Session: {face_count} face(s) detected total")


if __name__ == "__main__":
    main()
