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

echo "[1/3] Installing Python dependencies..."
pip3 install --quiet "opencv-python-headless>=4.8.1.78" numpy "Pillow>=10.2.0" 2>/dev/null || \
pip3 install "opencv-python-headless>=4.8.1.78" numpy "Pillow>=10.2.0"
echo "      Done."
echo ""

echo "[2/3] Downloading AI models..."
if [ -f "model_get.sh" ]; then
    chmod +x model_get.sh
    ./model_get.sh
else
    echo "      model_get.sh not found — skipping model download."
    echo "      Run ./model_get.sh manually to download models."
fi
echo ""

echo "[3/3] Verifying setup..."
python3 -c "import cv2; print('      OpenCV', cv2.__version__)" 2>/dev/null || echo "      WARNING: OpenCV not importable"
python3 -c "import numpy; print('      NumPy', numpy.__version__)" 2>/dev/null || echo "      WARNING: NumPy not importable"
python3 -c "from PIL import Image; print('      Pillow OK')" 2>/dev/null || echo "      WARNING: Pillow not importable"
echo ""

MODELS_DIR="models"
echo "================================================"
echo "  Setup complete!"
echo ""
echo "  Models in ./$MODELS_DIR/:"
ls -lh "$MODELS_DIR"/*.onnx 2>/dev/null | awk '{print "    " $NF " (" $5 ")"}' || echo "    (none downloaded)"
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
