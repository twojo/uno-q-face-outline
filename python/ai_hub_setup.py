# SPDX-FileCopyrightText: Copyright (C) 2025 Wojo
#
# SPDX-License-Identifier: MIT

"""
Qualcomm AI Hub — Model Download & Compile Helper

Downloads and compiles optimized face detection TFLite models for the
QRB2210 (Arduino Uno Q MPU). Run this script on a development machine
with internet access, then copy the resulting .tflite files to the
Uno Q's python/models/ directory.

Usage:

  # Option 1: Compile via Qualcomm AI Hub cloud (requires API token)
  python ai_hub_setup.py --compile --device QRB2210

  # Option 2: Download pre-exported TFLite from AI Hub (if available)
  python ai_hub_setup.py --download

  # Option 3: Just verify an existing model file
  python ai_hub_setup.py --verify python/models/face_det_lite.tflite

  # List available models
  python ai_hub_setup.py --list

  # Show system info / readiness check
  python ai_hub_setup.py --check

Requirements (install on dev machine, NOT on Uno Q):
  pip install qai-hub qai-hub-models numpy

On the Uno Q, only ai-edge-litert and numpy are needed at runtime.
ai-edge-litert is Google's successor to tflite-runtime with Python 3.13+ support.
The compile step runs in AI Hub's cloud — no local GPU required.
"""

import argparse
import os
import sys
import json
import shutil
import hashlib
from pathlib import Path

MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

SUPPORTED_MODELS = {
    "face_det_lite": {
        "display_name": "Lightweight Face Detection",
        "description": "Qualcomm's own face bounding box detector (878K params, ~194μs on S8E)",
        "qai_hub_id": "face_det_lite",
        "input_shape": (1, 3, 480, 640),
        "license": "BSD-3-Clause",
        "output_file": "face_det_lite.tflite",
        "recommended": True,
    },
    "mediapipe_face": {
        "display_name": "MediaPipe Face Detection",
        "description": "BlazeFace detector + landmark model (~0.6ms + 0.2ms on S23)",
        "qai_hub_id": "mediapipe_face",
        "input_shape": (1, 3, 256, 256),
        "license": "Apache-2.0",
        "output_file": "mediapipe_face_detector.tflite",
        "recommended": False,
    },
}

MANIFEST_FILE = MODELS_DIR / "manifest.json"


def print_banner():
    print()
    print("=" * 60)
    print("  Qualcomm AI Hub — Model Setup for QRB2210")
    print("  Wojo's Uno Q Face Outline Demo")
    print("=" * 60)
    print()


def check_qai_hub():
    try:
        import qai_hub as hub
        return True, hub
    except ImportError:
        return False, None


def check_qai_models():
    try:
        import qai_hub_models
        return True
    except ImportError:
        return False


def check_tflite_runtime():
    try:
        from ai_edge_litert.interpreter import Interpreter
        return True, "ai_edge_litert"
    except ImportError:
        pass
    try:
        from tflite_runtime.interpreter import Interpreter
        return True, "tflite_runtime"
    except ImportError:
        pass
    try:
        import tensorflow as tf
        _ = tf.lite.Interpreter
        return True, "tensorflow"
    except (ImportError, AttributeError):
        pass
    return False, None


def check_numpy():
    try:
        import numpy as np
        return True, np.__version__
    except ImportError:
        return False, None


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def save_manifest(model_name, info):
    manifest = {}
    if MANIFEST_FILE.exists():
        try:
            manifest = json.loads(MANIFEST_FILE.read_text())
        except Exception:
            pass
    manifest[model_name] = info
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2))


def cmd_check(args):
    print_banner()
    print("System Readiness Check")
    print("-" * 40)

    has_hub, hub = check_qai_hub()
    print(f"  qai_hub installed:        {'✓' if has_hub else '✗ (pip install qai-hub)'}")

    has_models = check_qai_models()
    print(f"  qai_hub_models installed: {'✓' if has_models else '✗ (pip install qai-hub-models)'}")

    has_tflite, tflite_backend = check_tflite_runtime()
    print(f"  TFLite runtime:           {'✓ (' + tflite_backend + ')' if has_tflite else '✗ (pip install ai-edge-litert)'}")

    has_numpy, np_ver = check_numpy()
    print(f"  numpy installed:          {'✓ (' + np_ver + ')' if has_numpy else '✗ (pip install numpy)'}")

    import platform
    print(f"  Python version:           {platform.python_version()}")
    print(f"  Platform:                 {platform.platform()}")
    print(f"  Machine:                  {platform.machine()}")
    print(f"  Models directory:         {MODELS_DIR}")

    existing = list(MODELS_DIR.glob("*.tflite"))
    if existing:
        print(f"\n  Existing models ({len(existing)}):")
        for f in existing:
            size_kb = f.stat().st_size / 1024
            print(f"    ✓ {f.name} ({size_kb:.0f} KB)")
    else:
        print(f"\n  No .tflite models found in {MODELS_DIR}")

    if has_hub:
        print("\n  AI Hub authentication:")
        try:
            client = hub.Client()
            devices = client.get_devices()
            qrb = [d for d in devices if "QRB2210" in str(d) or "RB1" in str(d) or "RB3" in str(d)]
            print(f"    ✓ Authenticated — {len(devices)} devices available")
            if qrb:
                print(f"    ✓ QRB2210-compatible devices: {', '.join(str(d) for d in qrb)}")
            else:
                print(f"    ⚠ No QRB2210 device found — will use QCS6490 as proxy")
        except Exception as e:
            print(f"    ✗ Not authenticated — run: qai-hub configure --api_token YOUR_TOKEN")
            print(f"      ({e})")

    print()
    return 0


def cmd_list(args):
    print_banner()
    print("Available Models for QRB2210")
    print("-" * 40)
    for name, info in SUPPORTED_MODELS.items():
        rec = " ★ RECOMMENDED" if info.get("recommended") else ""
        print(f"\n  {info['display_name']}{rec}")
        print(f"    ID:          {name}")
        print(f"    Description: {info['description']}")
        print(f"    Input:       {info['input_shape']}")
        print(f"    License:     {info['license']}")
        print(f"    Output:      {info['output_file']}")

        model_path = MODELS_DIR / info["output_file"]
        if model_path.exists():
            size_kb = model_path.stat().st_size / 1024
            print(f"    Status:      ✓ Downloaded ({size_kb:.0f} KB)")
        else:
            print(f"    Status:      ✗ Not downloaded")
    print()
    return 0


def cmd_compile(args):
    print_banner()

    has_hub, hub = check_qai_hub()
    if not has_hub:
        print("ERROR: qai_hub not installed.")
        print("  pip install qai-hub qai-hub-models")
        return 1

    has_models = check_qai_models()
    if not has_models:
        print("ERROR: qai_hub_models not installed.")
        print("  pip install qai-hub-models")
        return 1

    model_name = args.model
    if model_name not in SUPPORTED_MODELS:
        print(f"ERROR: Unknown model '{model_name}'")
        print(f"  Available: {', '.join(SUPPORTED_MODELS.keys())}")
        return 1

    model_info = SUPPORTED_MODELS[model_name]
    device_name = args.device
    quantize = args.quantize

    print(f"Compiling: {model_info['display_name']}")
    print(f"  Target device: {device_name}")
    print(f"  Runtime:       TFLite")
    print(f"  Quantization:  {quantize or 'none (float32)'}")
    print(f"  Output:        {MODELS_DIR / model_info['output_file']}")
    print()

    try:
        import torch

        if model_name == "face_det_lite":
            from qai_hub_models.models.face_det_lite import Model
        elif model_name == "mediapipe_face":
            from qai_hub_models.models.mediapipe_face import Model
        else:
            print(f"ERROR: No import path for model '{model_name}'")
            return 1

        print("Loading pretrained model...")
        torch_model = Model.from_pretrained()

        print(f"Resolving device: {device_name}")
        device = hub.Device(device_name)

        print("Tracing model...")
        sample_inputs = torch_model.sample_inputs()
        traced = torch.jit.trace(
            torch_model,
            [torch.tensor(data[0]) for _, data in sample_inputs.items()]
        )

        compile_options = "--target_runtime tflite"
        if quantize:
            compile_options += f" --quantize {quantize}"

        print("Submitting compile job to AI Hub cloud...")
        print("  (This may take 2-5 minutes)")
        compile_job = hub.submit_compile_job(
            model=traced,
            device=device,
            input_specs=torch_model.get_input_spec(),
            options=compile_options,
        )

        print(f"  Job submitted: {compile_job}")

        print("Waiting for compilation...")
        target_model = compile_job.get_target_model()

        output_path = MODELS_DIR / model_info["output_file"]
        print(f"Downloading compiled model to {output_path}...")
        target_model.download(str(output_path))

        size_kb = output_path.stat().st_size / 1024
        sha = file_hash(output_path)
        print(f"\n✓ Model saved: {output_path}")
        print(f"  Size:   {size_kb:.0f} KB")
        print(f"  SHA256: {sha}")

        save_manifest(model_name, {
            "file": model_info["output_file"],
            "device": device_name,
            "quantize": quantize,
            "size_kb": round(size_kb),
            "sha256_prefix": sha,
            "compiled_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
        })

        print("\nNext steps:")
        print(f"  1. Copy {output_path} to your Uno Q")
        print(f"  2. On the Uno Q, install: pip install ai-edge-litert numpy")
        print(f"  3. The face detector will auto-discover the model on next boot")
        print()
        return 0

    except Exception as e:
        print(f"\nERROR during compilation: {e}")
        print("\nTroubleshooting:")
        print("  1. Ensure you're authenticated: qai-hub configure --api_token YOUR_TOKEN")
        print("  2. Check device availability: python -c \"import qai_hub; print(qai_hub.Client().get_devices())\"")
        print(f"  3. If '{device_name}' isn't available, try: --device 'QCS6490 (Proxy)'")
        return 1


def cmd_download(args):
    print_banner()

    model_name = args.model
    if model_name not in SUPPORTED_MODELS:
        print(f"ERROR: Unknown model '{model_name}'")
        print(f"  Available: {', '.join(SUPPORTED_MODELS.keys())}")
        return 1

    model_info = SUPPORTED_MODELS[model_name]

    print(f"Attempting to download pre-built model: {model_info['display_name']}")
    print()

    has_hub, hub = check_qai_hub()
    if not has_hub:
        print("qai_hub not installed — trying direct download...")
        print()
        print("For manual setup:")
        print(f"  1. Visit https://aihub.qualcomm.com/models/{model_info['qai_hub_id']}")
        print(f"  2. Click 'Download Model' → select TFLite runtime")
        print(f"  3. Save the .tflite file as: {MODELS_DIR / model_info['output_file']}")
        print()
        print("Or install qai-hub for automated download:")
        print("  pip install qai-hub qai-hub-models")
        return 1

    print("NOTE: --download cannot produce a .tflite file directly.")
    print("      TFLite models must be compiled via AI Hub cloud.")
    print()
    print("Options:")
    print(f"  1. Compile via cloud (recommended):")
    print(f"     python ai_hub_setup.py --compile --model {model_name} --device QRB2210")
    print()
    print(f"  2. Download manually from AI Hub website:")
    print(f"     a. Visit https://aihub.qualcomm.com/models/{model_info['qai_hub_id']}")
    print(f"     b. Click 'Download Model' → select TFLite runtime")
    print(f"     c. Save the .tflite file as: {MODELS_DIR / model_info['output_file']}")
    print()
    print(f"  3. Drop any .tflite file into: {MODELS_DIR}/")
    print(f"     The detector auto-discovers all .tflite files at boot.")
    return 1


def cmd_verify(args):
    print_banner()

    model_path = Path(args.file)
    if not model_path.exists():
        print(f"ERROR: File not found: {model_path}")
        return 1

    size_kb = model_path.stat().st_size / 1024
    sha = file_hash(model_path)

    print(f"Verifying: {model_path}")
    print(f"  Size:   {size_kb:.0f} KB")
    print(f"  SHA256: {sha}")

    has_tflite, backend = check_tflite_runtime()
    if not has_tflite:
        print(f"\n  ⚠ Cannot verify inference — no TFLite runtime installed")
        print(f"    Install: pip install ai-edge-litert")
        return 0

    print(f"\n  Loading with {backend}...")
    try:
        if backend == "ai_edge_litert":
            from ai_edge_litert.interpreter import Interpreter
        elif backend == "tflite_runtime":
            from tflite_runtime.interpreter import Interpreter
        else:
            import tensorflow as tf
            Interpreter = tf.lite.Interpreter

        interpreter = Interpreter(model_path=str(model_path))
        interpreter.allocate_tensors()

        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()

        print(f"  ✓ Model loaded successfully")
        print(f"\n  Inputs ({len(input_details)}):")
        for inp in input_details:
            print(f"    [{inp['index']}] {inp['name']}: shape={inp['shape']} dtype={inp['dtype']}")
        print(f"\n  Outputs ({len(output_details)}):")
        for out in output_details:
            print(f"    [{out['index']}] {out['name']}: shape={out['shape']} dtype={out['dtype']}")

        import numpy as np
        for inp in input_details:
            test_data = np.zeros(inp['shape'], dtype=inp['dtype'])
            interpreter.set_tensor(inp['index'], test_data)

        import time
        t0 = time.time()
        interpreter.invoke()
        elapsed_ms = (time.time() - t0) * 1000

        print(f"\n  ✓ Test inference OK ({elapsed_ms:.1f} ms on this machine)")
        print(f"    (QRB2210 inference will differ — profile via AI Hub for accurate timing)")

        return 0

    except Exception as e:
        print(f"\n  ✗ Verification failed: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Qualcomm AI Hub model setup for QRB2210 face detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --check                           System readiness check
  %(prog)s --list                            List available models
  %(prog)s --compile --model face_det_lite   Compile via AI Hub cloud
  %(prog)s --compile --quantize w8a8         Compile with INT8 quantization
  %(prog)s --download --model face_det_lite  Download pre-built model
  %(prog)s --verify models/face_det_lite.tflite  Verify a model file
        """
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="Check system readiness")
    group.add_argument("--list", action="store_true", help="List available models")
    group.add_argument("--compile", action="store_true", help="Compile model via AI Hub cloud")
    group.add_argument("--download", action="store_true", help="Download pre-built model")
    group.add_argument("--verify", metavar="FILE", help="Verify a .tflite model file")

    parser.add_argument("--model", default="face_det_lite",
                        choices=list(SUPPORTED_MODELS.keys()),
                        help="Model to compile/download (default: face_det_lite)")
    parser.add_argument("--device", default="QRB2210",
                        help="AI Hub target device (default: QRB2210)")
    parser.add_argument("--quantize", default=None,
                        choices=["w8a8", "w8a16", "w4a16"],
                        help="Quantization level (default: none/float32)")

    args = parser.parse_args()

    if args.check:
        return cmd_check(args)
    elif args.list:
        return cmd_list(args)
    elif args.compile:
        return cmd_compile(args)
    elif args.download:
        return cmd_download(args)
    elif args.verify:
        return cmd_verify(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
