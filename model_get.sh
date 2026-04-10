#!/bin/bash
#
# Wojo's Uno Q Face Outline Tracker Demo — Model Downloader (yzma-style)
#
# Usage:
#   ./model_get.sh                          # download all default models
#   ./model_get.sh -u <huggingface_url>     # download a custom ONNX model
#   ./model_get.sh --list                   # show available models

set -e

MODELS_DIR="models"
mkdir -p "$MODELS_DIR"

MODELS=(
    "face-detection|face_detection_yunet.onnx|https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx|YuNet face detector (75K params, ~233 KB)"
    "face-detection-int8|face_detection_yunet_int8.onnx|https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar_int8.onnx|YuNet INT8 quantized (faster on ARM)"
    "face-mesh|face_mesh_192x192.onnx|https://github.com/PINTO0309/facemesh_onnx_tensorrt/raw/main/face_mesh_Nx3x192x192_post.onnx|468-landmark face mesh (ONNX)"
)

show_list() {
    echo ""
    echo "Available models:"
    echo ""
    for entry in "${MODELS[@]}"; do
        IFS='|' read -r name file url desc <<< "$entry"
        status="not downloaded"
        if [ -f "$MODELS_DIR/$file" ]; then
            size=$(du -h "$MODELS_DIR/$file" | cut -f1)
            status="downloaded ($size)"
        fi
        echo "  $name"
        echo "    $desc"
        echo "    Status: $status"
        echo ""
    done
}

download_model() {
    local name="$1"
    for entry in "${MODELS[@]}"; do
        IFS='|' read -r mname file url desc <<< "$entry"
        if [ "$mname" = "$name" ]; then
            if [ -f "$MODELS_DIR/$file" ]; then
                echo "Already downloaded: $MODELS_DIR/$file"
                return 0
            fi
            echo "Downloading $mname..."
            curl -fsSL -o "$MODELS_DIR/$file" "$url"
            echo "Saved to $MODELS_DIR/$file"
            return 0
        fi
    done
    echo "Unknown model: $name"
    echo "Run: ./model_get.sh --list"
    return 1
}

download_url() {
    local url="$1"
    local filename=$(basename "$url")
    echo "Downloading $filename..."
    curl -fsSL -o "$MODELS_DIR/$filename" "$url"
    echo "Saved to $MODELS_DIR/$filename"
}

download_all() {
    echo "Downloading default models..."
    echo ""
    download_model "face-detection"
    download_model "face-mesh"
    echo ""
    echo "Done. Models in ./$MODELS_DIR/"
}

case "${1:-}" in
    --list|-l)
        show_list
        ;;
    -u|--url)
        if [ -z "${2:-}" ]; then
            echo "Usage: ./model_get.sh -u <url>"
            exit 1
        fi
        download_url "$2"
        ;;
    "")
        download_all
        ;;
    *)
        download_model "$1"
        ;;
esac
