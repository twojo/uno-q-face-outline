#!/bin/bash
#
# Wojo's Uno Q Face Outline Tracker Demo — One-Command Setup
#
# Like "yzma install" + "yzma model get" but for face detection.
# Run this on your Uno Q via SSH:
#
#   ./setup.sh
#
# Then run the face tracker:
#
#   python3 direct/face_tracker.py          # standalone (no App Lab)
#   arduino-app run .                       # full App Lab with WebUI + sketch

set -e

echo ""
echo "================================================"
echo "  Wojo's Face Tracker — Setup"
echo "  Arduino Uno Q (Qualcomm QRB2210 + STM32U585)"
echo "================================================"
echo ""

MODELS_DIR="models"
mkdir -p "$MODELS_DIR"

echo "[1/3] Installing Python dependencies..."
pip3 install --quiet "opencv-python-headless>=4.8.1.78" numpy 2>/dev/null || \
pip3 install "opencv-python-headless>=4.8.1.78" numpy
echo "      Done."
echo ""

echo "[2/3] Downloading face detection model (YuNet, 233 KB)..."
if [ -f "$MODELS_DIR/face_detection_yunet.onnx" ]; then
    echo "      Already exists — skipping."
else
    curl -fsSL -o "$MODELS_DIR/face_detection_yunet.onnx" \
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
    echo "      Downloaded."
fi
echo ""

echo "[3/3] Downloading face mesh model (468 landmarks, ONNX)..."
if [ -f "$MODELS_DIR/face_mesh_192x192.onnx" ]; then
    echo "      Already exists — skipping."
else
    curl -fsSL -o "$MODELS_DIR/face_mesh_192x192.onnx" \
        "https://github.com/PINTO0309/facemesh_onnx_tensorrt/raw/main/face_mesh_Nx3x192x192_post.onnx"
    echo "      Downloaded."
fi
echo ""

echo "================================================"
echo "  Setup complete!"
echo ""
echo "  Models in ./$MODELS_DIR/:"
ls -lh "$MODELS_DIR"/*.onnx 2>/dev/null | awk '{print "    " $NF " (" $5 ")"}'
echo ""
echo "  Run options:"
echo ""
echo "    # Standalone face detection (no App Lab):"
echo "    python3 direct/face_tracker.py"
echo ""
echo "    # Full App Lab with WebUI + MCU sketch:"
echo "    arduino-app run ."
echo ""
echo "================================================"
