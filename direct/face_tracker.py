#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (C) 2025 Wojo
# SPDX-License-Identifier: MIT
#
# Wojo's Face Tracker — Direct SSH Version
#
# SSH into your Uno Q and run:
#
#   ./setup.sh                        # one-time: installs deps + downloads models
#   python3 direct/face_tracker.py    # start tracking
#
# Uses OpenCV's YuNet face detector (75K params, 233 KB) and
# optionally the 468-landmark face mesh model via ONNX Runtime.
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
        print("[OK] Face mesh model loaded (468 landmarks)")
    else:
        print("[INFO] Face mesh model not found — run ./setup.sh to download")
except ImportError:
    print("[INFO] onnxruntime not installed — face mesh disabled")
    print("       pip3 install onnxruntime")


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
        print("       Run ./setup.sh first to download models")
        sys.exit(1)

    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)

    if not cap.isOpened():
        print("ERROR: Cannot open camera")
        print(f"       Tried camera index {CAMERA_INDEX}")
        print("       Check USB webcam connection")
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
    print("  Wojo's Face Tracker — Running")
    print(f"  Camera: {FRAME_W}x{FRAME_H} @ index {CAMERA_INDEX}")
    print(f"  Model: YuNet ({os.path.getsize(FACE_MODEL) // 1024} KB)")
    print(f"  Mesh: {'enabled (468 landmarks)' if HAS_MESH else 'disabled'}")
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
