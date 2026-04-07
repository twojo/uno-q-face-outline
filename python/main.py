# SPDX-FileCopyrightText: Copyright (C) 2025 Wojo
#
# SPDX-License-Identifier: MIT

# Wojo's Uno Q Face Outline Demo — MPU Entry Point
#
# This script runs on the Linux side (Qualcomm QRB2210) and acts as
# the coordinator between three systems:
#
#   Browser (MediaPipe)  <--WebSocket-->  MPU (this script)  <--Bridge-->  MCU (sketch.ino)
#
# ── Startup Diagnostics ──
# Before the app starts serving, this script runs a comprehensive
# set of checks and dumps as much info as possible to the terminal.
# The Uno Q can be picky with network and USB connections, so having
# detailed diagnostic output on every boot helps catch issues early.
#
# The boot sequence:
#   1. Print banner with board/OS specs
#   2. Check network interfaces and connectivity
#   3. Test reachability of CDN endpoints (MediaPipe, Google Fonts)
#   4. Print folder tree of the project
#   5. Report system resources (CPU, RAM, disk, uptime)
#   6. Initialize Bridge and WebUI
#   7. Scroll IP + status on LED matrix
#   8. Wait for browser connection
#
# Dependencies: stdlib + App Lab SDK. Optional: tflite-runtime, numpy,
# opencv-python-headless for on-device face detection via AI Hub models.

from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
import json
import socket
import time
import threading
import os
import sys
import platform
import subprocess
import signal

try:
    from face_detector_mpu import FaceDetectorMPU, find_models
    _ai_hub_import_ok = True
except ImportError:
    _ai_hub_import_ok = False

logger = Logger("face-demo")
ui = WebUI()

BOOT_START = time.time()

mpu_detector = None

_bridge_ready = False


def safe_bridge_call(method, *args):
    """Call a Bridge method with error handling. If the MCU hasn't
    signalled mcu_ready yet or the Bridge raises, the error is logged
    but never propagated — the demo keeps running in browser-only mode."""
    try:
        Bridge.call(method, *args)
    except Exception as e:
        logger.error(f"[BRIDGE] safe_bridge_call({method}) failed: {e}")


# ── Terminal Formatting Helpers ──

def divider():
    logger.info("─" * 56)

def section(title):
    logger.info("")
    divider()
    logger.info(f"  {title}")
    divider()

def kv(key, value, indent=2):
    padding = " " * indent
    label = f"{key}".ljust(24)
    logger.info(f"{padding}{label}: {value}")

def ok(msg):
    logger.info(f"  ✓ {msg}")

def warn(msg):
    logger.info(f"  ⚠ {msg}")

def fail(msg):
    logger.info(f"  ✗ {msg}")


# ── System Info ──

def get_ip_address():
    """Return the device's primary LAN IP by briefly opening a UDP
    socket to a public DNS server. No data is actually sent."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(3)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "No IP"

def get_all_ips():
    """Return all network interface IPs by parsing hostname output."""
    ips = []
    try:
        result = subprocess.run(
            ["hostname", "-I"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            ips = result.stdout.strip().split()
    except Exception:
        pass
    if not ips:
        ip = get_ip_address()
        if ip != "No IP":
            ips = [ip]
    return ips

def get_uptime():
    """Read system uptime from /proc/uptime. Returns formatted string."""
    try:
        with open("/proc/uptime", "r") as f:
            secs = float(f.read().split()[0])
        days = int(secs // 86400)
        hrs = int((secs % 86400) // 3600)
        mins = int((secs % 3600) // 60)
        if days > 0:
            return f"{days}d {hrs}h {mins}m"
        elif hrs > 0:
            return f"{hrs}h {mins}m"
        else:
            return f"{mins}m {int(secs % 60)}s"
    except Exception:
        return "unknown"

def get_cpu_info():
    """Parse /proc/cpuinfo for model name and core count."""
    model = "unknown"
    cores = 0
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if line.startswith("model name") and model == "unknown":
                    model = line.split(":")[1].strip()
                if line.startswith("processor"):
                    cores += 1
    except Exception:
        pass
    return model, cores

def get_mem_info():
    """Parse /proc/meminfo for total and available RAM."""
    total = avail = 0
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1]) // 1024
                elif line.startswith("MemAvailable:"):
                    avail = int(line.split()[1]) // 1024
    except Exception:
        pass
    return total, avail

def get_disk_info():
    """Get disk usage for the root filesystem."""
    try:
        st = os.statvfs("/")
        total = (st.f_blocks * st.f_frsize) // (1024 * 1024)
        free = (st.f_bavail * st.f_frsize) // (1024 * 1024)
        used = total - free
        pct = round((used / total) * 100, 1) if total > 0 else 0
        return total, used, free, pct
    except Exception:
        return 0, 0, 0, 0

def get_kernel_version():
    """Return the kernel version string."""
    try:
        return platform.release()
    except Exception:
        return "unknown"

def check_dns(host="google.com"):
    """Test DNS resolution. Returns resolved IP or None."""
    try:
        ip = socket.gethostbyname(host)
        return ip
    except Exception:
        return None

def check_http_reachable(url, timeout=5):
    """Test if a URL is reachable via a raw HTTP HEAD request.
    Uses only stdlib (no requests/urllib3) to avoid dependencies."""
    try:
        import urllib.request
        req = urllib.request.Request(url, method="HEAD")
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status
    except Exception as e:
        return str(e)

def print_folder_tree(root, prefix="", max_depth=3, current_depth=0):
    """Print a folder tree to the logger. Skips hidden dirs,
    __pycache__, node_modules, and .git to keep it readable."""
    skip = {".git", "__pycache__", "node_modules", ".local",
            ".cache", ".pythonlibs", ".config", "venv", ".upm"}
    if current_depth >= max_depth:
        return
    try:
        entries = sorted(os.listdir(root))
    except PermissionError:
        return
    dirs = [e for e in entries if os.path.isdir(os.path.join(root, e)) and e not in skip and not e.startswith(".")]
    files = [e for e in entries if os.path.isfile(os.path.join(root, e)) and not e.startswith(".")]

    for f in files:
        size = os.path.getsize(os.path.join(root, f))
        size_str = f"{size}B" if size < 1024 else f"{size // 1024}KB"
        logger.info(f"{prefix}├── {f} ({size_str})")
    for i, d in enumerate(dirs):
        connector = "└── " if i == len(dirs) - 1 and not files else "├── "
        logger.info(f"{prefix}{connector}{d}/")
        ext = "    " if i == len(dirs) - 1 else "│   "
        print_folder_tree(os.path.join(root, d), prefix + ext,
                         max_depth, current_depth + 1)


# ── Auto Model Setup ──

def _auto_setup_models():
    """Attempt to automatically set up TFLite models if python/models/
    is empty. Tries running ai_hub_setup.py --compile, then --download.
    Returns the result of find_models() after the attempt (may still
    be empty if setup tools are not available)."""
    setup_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_hub_setup.py")
    if not os.path.exists(setup_script):
        logger.info("    ai_hub_setup.py not found — skipping auto-setup")
        return {}

    models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    os.makedirs(models_dir, exist_ok=True)

    for action in ["--compile", "--download"]:
        try:
            logger.info(f"    Running: python ai_hub_setup.py {action} --model face_det_lite")
            result = subprocess.run(
                [sys.executable, setup_script, action, "--model", "face_det_lite"],
                capture_output=True, text=True, timeout=120, cwd=os.path.dirname(setup_script)
            )
            if result.returncode == 0:
                logger.info(f"    Auto-setup ({action}) succeeded")
                from face_detector_mpu import find_models
                return find_models()
            else:
                last_lines = (result.stdout + result.stderr).strip().split("\n")[-3:]
                for line in last_lines:
                    if line.strip():
                        logger.info(f"    {line.strip()}")
        except subprocess.TimeoutExpired:
            logger.info(f"    Auto-setup ({action}) timed out after 120s")
        except Exception as e:
            logger.info(f"    Auto-setup ({action}) error: {e}")

    logger.info("    Auto-setup could not produce a model — continuing in browser-only mode")
    return {}


# ── Boot Diagnostics ──
# Run all checks before the app starts serving. This prints
# everything to the terminal so you have a complete snapshot
# of the system state on every boot.

def run_boot_diagnostics():
    """Run full system diagnostics and print to terminal."""

    section("WOJO'S UNO Q FACE OUTLINE DEMO — MPU BOOT")
    kv("App", "Face Outline Demo v1.0")
    kv("Python", platform.python_version())
    kv("Platform", platform.platform())
    kv("Machine", platform.machine())
    kv("Hostname", socket.gethostname())
    kv("Kernel", get_kernel_version())
    kv("PID", os.getpid())
    kv("Working directory", os.getcwd())
    kv("Boot time", time.strftime("%Y-%m-%d %H:%M:%S"))

    # --- System Resources ---
    section("SYSTEM RESOURCES")
    cpu_model, cpu_cores = get_cpu_info()
    kv("CPU model", cpu_model)
    kv("CPU cores", cpu_cores)

    mem_total, mem_avail = get_mem_info()
    mem_used = mem_total - mem_avail
    mem_pct = round((mem_used / mem_total) * 100, 1) if mem_total > 0 else 0
    kv("RAM total", f"{mem_total} MB")
    kv("RAM available", f"{mem_avail} MB ({100 - mem_pct}% free)")
    kv("RAM used", f"{mem_used} MB ({mem_pct}%)")

    disk_total, disk_used, disk_free, disk_pct = get_disk_info()
    kv("Disk total", f"{disk_total} MB")
    kv("Disk used", f"{disk_used} MB ({disk_pct}%)")
    kv("Disk free", f"{disk_free} MB")

    kv("System uptime", get_uptime())

    # --- Network ---
    section("NETWORK DIAGNOSTICS")
    primary_ip = get_ip_address()
    all_ips = get_all_ips()
    kv("Primary IP", primary_ip)
    kv("All IPs", ", ".join(all_ips) if all_ips else "none")
    kv("Hostname (FQDN)", socket.getfqdn())

    dns_result = check_dns("google.com")
    if dns_result:
        ok(f"DNS resolution OK — google.com → {dns_result}")
    else:
        fail("DNS resolution FAILED — check /etc/resolv.conf")

    dns_cdn = check_dns("cdn.jsdelivr.net")
    if dns_cdn:
        ok(f"CDN DNS OK — cdn.jsdelivr.net → {dns_cdn}")
    else:
        warn("CDN DNS FAILED — MediaPipe may not load in browser")

    # --- CDN Connectivity ---
    # These are the URLs the browser will try to fetch. If the Uno Q
    # can't reach them, the face tracker won't work. We check from
    # the MPU side as an early warning.
    section("CDN REACHABILITY (browser will need these)")

    cdn_checks = [
        ("MediaPipe WASM", "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.3/+esm"),
        ("MediaPipe Model", "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"),
        ("Google Fonts", "https://fonts.googleapis.com/css2?family=Inter"),
    ]

    for name, url in cdn_checks:
        result = check_http_reachable(url)
        if isinstance(result, int) and result < 400:
            ok(f"{name}: HTTP {result} OK")
        else:
            warn(f"{name}: {result}")
            if "mediapipe" in name.lower():
                logger.info(f"    ↳ Face tracking will NOT work without this!")

    # --- Project Files ---
    section("PROJECT FOLDER TREE")
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print_folder_tree(project_root, "  ", max_depth=3)

    # --- App Lab Config ---
    section("APP LAB CONFIGURATION")
    app_yaml = os.path.join(project_root, "app.yaml")
    if os.path.exists(app_yaml):
        ok("app.yaml found")
        try:
            with open(app_yaml, "r") as f:
                for line in f:
                    line = line.rstrip()
                    if line and not line.startswith("#"):
                        logger.info(f"    {line}")
        except Exception:
            pass
    else:
        fail("app.yaml NOT FOUND — App Lab won't recognize this project")

    sketch_yaml = os.path.join(project_root, "sketch", "sketch.yaml")
    if os.path.exists(sketch_yaml):
        ok("sketch/sketch.yaml found")
    else:
        warn("sketch/sketch.yaml missing")

    assets_html = os.path.join(project_root, "assets", "index.html")
    if os.path.exists(assets_html):
        size = os.path.getsize(assets_html)
        ok(f"assets/index.html found ({size // 1024} KB)")
    else:
        fail("assets/index.html NOT FOUND — frontend will not load")

    # --- AI Hub / On-Device Detection ---
    section("AI HUB — ON-DEVICE FACE DETECTION")
    global mpu_detector

    if not _ai_hub_import_ok:
        warn("face_detector_mpu module not available (import failed)")
        kv("On-device detection", "DISABLED — browser-only mode")
    else:
        try:
            from face_detector_mpu import (
                _tflite_available, _tflite_backend,
                _numpy_available, _cv2_available,
                find_camera,
            )
            kv("TFLite runtime", f"{'✓ ' + _tflite_backend if _tflite_available else '✗ not installed'}")
            kv("numpy", f"{'✓' if _numpy_available else '✗ not installed'}")
            kv("OpenCV", f"{'✓' if _cv2_available else '✗ not installed'}")

            models = find_models()
            if not models:
                kv("Models found", "0")
                warn("No .tflite models in python/models/ — attempting auto-setup...")
                models = _auto_setup_models()

            if models:
                kv("Models found", len(models))
                for name, info in models.items():
                    ok(f"{name} ({info['size_kb']} KB) — {info['path']}")
            else:
                kv("Models found", "0")
                warn("No .tflite models available after auto-setup attempt")
                logger.info("    Manual setup: python ai_hub_setup.py --compile --model face_det_lite")

            cam_dev, cam_idx = find_camera()
            kv("Camera device", f"{'✓ ' + cam_dev if cam_dev else '✗ not found'}")

            mpu_detector = FaceDetectorMPU(logger=logger)
            init_ok = mpu_detector.initialize()

            if init_ok:
                status = mpu_detector.get_status_dict()
                kv("Detector status", f"✓ {status['status']} — {status['detail']}")
                kv("On-device detection", "AVAILABLE")
            else:
                status = mpu_detector.get_status_dict()
                kv("Detector status", f"⚠ {status['status']} — {status['detail']}")
                kv("On-device detection", "UNAVAILABLE — falling back to browser-only mode")
                mpu_detector = None

        except Exception as e:
            warn(f"AI Hub init error: {e}")
            kv("On-device detection", "DISABLED — browser-only mode")
            mpu_detector = None

    # --- Boot Summary ---
    boot_elapsed = time.time() - BOOT_START
    section("BOOT DIAGNOSTICS COMPLETE")
    kv("Diagnostics took", f"{boot_elapsed:.2f}s")
    kv("Primary IP", primary_ip)
    kv("DNS", "OK" if dns_result else "FAILED")
    kv("CDN reachable", "checked (see above)")
    kv("On-device AI", "ACTIVE" if mpu_detector else "browser-only")
    logger.info("")
    logger.info("  Open your browser to:")
    logger.info(f"    http://{primary_ip}:<port>/")
    logger.info("")
    logger.info("  The LED matrix will scroll the IP address shortly.")
    divider()
    logger.info("")


# Run diagnostics immediately on import (before app starts)
run_boot_diagnostics()


# ── Face State ──

face_state = {
    "faces_detected": 0,
    "blink_count": 0,
    "expression": "neutral",
    "pupil_l_mm": 0.0,
    "pupil_r_mm": 0.0,
    "yaw": 0.0,
    "pitch": 0.0,
    "device_mode": "uno_q"
}

last_face_present = False


# ── Startup Sequence (background thread) ──
# After diagnostics complete, this thread handles the LED matrix
# boot sequence: scrolls the IP, then "Face Demo Ready".

def startup_sequence():
    """Runs once at boot in a background thread. Scrolls diagnostic
    info across the LED matrix so the user can see board status
    even without a terminal connected."""
    time.sleep(2)
    ip = get_ip_address()

    logger.info(f"[STARTUP] Scrolling IP on LED matrix: {ip}")
    safe_bridge_call("scroll_text", f"  IP: {ip}  ")
    time.sleep(8)

    mem_total, mem_avail = get_mem_info()
    safe_bridge_call("scroll_text", f"  RAM: {mem_avail}/{mem_total}MB  ")
    time.sleep(6)

    safe_bridge_call("scroll_text", f"  {platform.machine()} {get_kernel_version()[:12]}  ")
    time.sleep(6)

    if mpu_detector and mpu_detector.available:
        safe_bridge_call("scroll_text", "  AI: ON-DEVICE  ")
        time.sleep(4)
        started = mpu_detector.start()
        if started:
            logger.info("[STARTUP] On-device face detection started")
            safe_bridge_call("set_rgb", "cyan")
            time.sleep(1)
            safe_bridge_call("set_rgb", "off")
        else:
            logger.info("[STARTUP] On-device detection available but could not start capture")

    safe_bridge_call("scroll_text", "  Face Demo Ready  ")
    logger.info("[STARTUP] LED matrix boot sequence complete")

startup_thread = threading.Thread(target=startup_sequence, daemon=True)
startup_thread.start()


# ── MPU Detector Callbacks ──
# When on-device detection is active, face results from the MPU
# bypass the browser entirely and go straight to the MCU.

mpu_last_face_present = False

def on_mpu_faces(faces):
    global mpu_last_face_present
    n = len(faces)
    face_state["faces_detected"] = n

    if not mpu_last_face_present:
        logger.info(f"[AI-HUB] Face appeared (on-device) — {n} face(s)")
        safe_bridge_call("flash_face", 3)
    else:
        safe_bridge_call("show_face")

    mpu_last_face_present = True

    ui.send_message("mpu_face_data", json.dumps({
        "faces": n,
        "source": "mpu",
        "inference_ms": round(mpu_detector.last_inference_ms, 1) if mpu_detector else 0,
        "detections": [{"box": f["box"], "score": round(f["score"], 3)} for f in faces],
    }))

def on_mpu_no_faces():
    global mpu_last_face_present
    if mpu_last_face_present:
        logger.info("[AI-HUB] Face lost (on-device)")
        safe_bridge_call("show_no_face")
        face_state["faces_detected"] = 0
    mpu_last_face_present = False

if mpu_detector:
    mpu_detector.on_faces(on_mpu_faces)
    mpu_detector.on_no_faces(on_mpu_no_faces)


# ── Bridge Providers (MCU -> MPU) ──

def _send_mpu_ack():
    """Send mpu_ack in a separate thread to avoid blocking the Bridge
    read loop. Bridge.call() waits for a response, but the read loop
    cannot process responses while it is executing a provider callback.
    Dispatching to a thread breaks that deadlock."""
    time.sleep(0.1)
    safe_bridge_call("mpu_ack")

def on_mcu_ready():
    """Called by the MCU sketch after Bridge.begin() completes on
    the STM32 side. Confirms the two processors are communicating.
    Sends mpu_ack back (via a background thread) so the MCU stops
    retrying. The thread dispatch avoids a deadlock: Bridge.call()
    inside a provider callback would block the read loop that needs
    to process the response."""
    global _bridge_ready
    _bridge_ready = True
    logger.info("[BRIDGE] MCU ready — STM32 <-> QRB2210 link confirmed")
    logger.info("[BRIDGE] MCU can now receive scroll_text, show_face, etc.")
    threading.Thread(target=_send_mpu_ack, daemon=True).start()

Bridge.provide("mcu_ready", on_mcu_ready)

def on_mcu_status_report(report):
    """Receive periodic status reports from the MCU. Logs them so
    they appear in the terminal alongside MPU diagnostics."""
    logger.info(f"[MCU-STATUS] {report}")

Bridge.provide("mcu_status_report", on_mcu_status_report)


# ── WebSocket Handlers (Browser -> MPU) ──

def on_browser_connect(sid):
    """Push the current face state to a newly connected browser so
    its UI starts in sync with reality. Also log connection details."""
    try:
        logger.info(f"[WS] Browser connected: {sid}")
        logger.info(f"[WS] Sending initial state: {json.dumps(face_state)}")
        ui.send_message("state_update", json.dumps(face_state))

        safe_bridge_call("set_rgb", "blue")
        time.sleep(0.3)
        safe_bridge_call("set_rgb", "green")
    except Exception as e:
        logger.error(f"[WS] on_browser_connect error: {e}")

def on_browser_disconnect(sid):
    """Handle browser disconnection gracefully."""
    try:
        logger.info(f"[WS] Browser disconnected: {sid}")
        safe_bridge_call("set_rgb", "red")
    except Exception as e:
        logger.error(f"[WS] on_browser_disconnect error: {e}")

ui.on_connect(on_browser_connect)
ui.on_disconnect(on_browser_disconnect)


def on_face_data(sid, data):
    """Handle face tracking telemetry from the browser. The frontend
    sends a compact JSON payload roughly every 500ms containing face
    count, blink count, dominant expression, pupil diameters, and
    head pose angles.

    When on-device detection is active, browser telemetry is ignored
    for MCU hardware control (LED/RGB) to avoid conflicting updates.
    The face_state dict is still updated for UI consistency.

    State transitions drive LED matrix + RGB LED updates:
      - No face -> face: flash smiley 3x, RGB green, relay ON
      - Face present:    show expression bitmap, RGB color-coded
      - Face -> no face: show X pattern, RGB red, relay OFF
    """
    global last_face_present

    mpu_active = mpu_detector and mpu_detector.running

    try:
        payload = json.loads(data) if isinstance(data, str) else data

        face_state["faces_detected"] = payload.get("faces", 0)
        face_state["blink_count"] = payload.get("blinks", 0)
        face_state["expression"] = payload.get("expression", "neutral")
        face_state["pupil_l_mm"] = payload.get("pupilL", 0.0)
        face_state["pupil_r_mm"] = payload.get("pupilR", 0.0)
        face_state["yaw"] = payload.get("yaw", 0.0)
        face_state["pitch"] = payload.get("pitch", 0.0)

        face_now = face_state["faces_detected"] > 0

        if not mpu_active:
            if face_now and not last_face_present:
                logger.info(f"[FACE] Face appeared — {face_state['faces_detected']} face(s)")
                safe_bridge_call("flash_face", 3)
                expr = face_state["expression"]
                if expr != "neutral":
                    time.sleep(0.5)
                    safe_bridge_call("show_expression", expr)

            elif face_now:
                expr = face_state["expression"]
                if expr != "neutral":
                    safe_bridge_call("show_expression", expr)
                else:
                    safe_bridge_call("show_face")

            elif not face_now and last_face_present:
                logger.info("[FACE] Face lost")
                safe_bridge_call("show_no_face")

        last_face_present = face_now

    except Exception as e:
        logger.error(f"face_data error: {e}")

ui.on_message("face_data", on_face_data)




def on_capture_snapshot(sid, data):
    """Acknowledge a snapshot request from the frontend."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    logger.info(f"[SNAPSHOT] Captured at {timestamp}")
    ui.send_message("snapshot_ack", json.dumps({
        "status": "ok",
        "timestamp": timestamp
    }))

ui.on_message("capture_snapshot", on_capture_snapshot)


# ── GPIO Control from Browser ──
# These handlers let the frontend toggle GPIO placeholders and
# the RGB LED. Useful for testing relay/buzzer/LED connections
# without reflashing the MCU.

def on_rgb_control(sid, data):
    """Set the MCU's RGB LED color from the browser."""
    try:
        payload = json.loads(data) if isinstance(data, str) else data
        color = payload.get("color", "off")
        logger.info(f"[RGB] Browser set color: {color}")
        safe_bridge_call("set_rgb", color)
    except Exception as e:
        logger.error(f"rgb_control error: {e}")

ui.on_message("rgb_control", on_rgb_control)

def on_gpio_control(sid, data):
    """Toggle a GPIO pin from the browser. Payload: {pin, state}"""
    try:
        payload = json.loads(data) if isinstance(data, str) else data
        pin = payload.get("pin", 0)
        state = payload.get("state", 0)
        logger.info(f"[GPIO] Browser set pin {pin} -> {state}")
        safe_bridge_call("set_gpio", f"{pin}:{state}")
    except Exception as e:
        logger.error(f"gpio_control error: {e}")

ui.on_message("gpio_control", on_gpio_control)


# ── AI Hub Status from Browser ──

def on_ai_status_request(sid, data):
    """Return on-device AI detection status to the browser."""
    if mpu_detector:
        status = mpu_detector.get_status_dict()
    else:
        status = {
            "available": False,
            "status": "disabled",
            "detail": "No TFLite model or runtime — browser-only mode",
            "model": None,
            "running": False,
            "fps": 0,
            "inference_ms": 0,
            "frame_count": 0,
            "detect_count": 0,
            "tflite_backend": None,
            "faces": 0,
        }
    ui.send_message("ai_status", json.dumps(status))

ui.on_message("ai_status_request", on_ai_status_request)


def on_ai_toggle(sid, data):
    """Start/stop on-device face detection from browser toggle."""
    if not mpu_detector:
        ui.send_message("ai_status", json.dumps({
            "available": False,
            "status": "disabled",
            "detail": "No TFLite model or runtime",
        }))
        return

    try:
        payload = json.loads(data) if isinstance(data, str) else data
        enable = payload.get("enable", False)

        if enable and not mpu_detector.running:
            started = mpu_detector.start()
            logger.info(f"[AI-HUB] On-device detection {'started' if started else 'failed to start'}")
        elif not enable and mpu_detector.running:
            mpu_detector.stop()
            logger.info("[AI-HUB] On-device detection stopped by browser")

        ui.send_message("ai_status", json.dumps(mpu_detector.get_status_dict()))
    except Exception as e:
        logger.error(f"ai_toggle error: {e}")

ui.on_message("ai_toggle", on_ai_toggle)


# ── Graceful Shutdown ──

_shutting_down = False

def _shutdown_handler(signum, frame):
    global _shutting_down
    if _shutting_down:
        return
    _shutting_down = True
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logger.info(f"[SHUTDOWN] Received {sig_name} — cleaning up...")
    try:
        if mpu_detector and mpu_detector.running:
            mpu_detector.stop()
            logger.info("[SHUTDOWN] On-device detector stopped")
    except Exception as e:
        logger.error(f"[SHUTDOWN] Error stopping detector: {e}")
    try:
        safe_bridge_call("set_rgb", "red")
        safe_bridge_call("show_no_face")
        logger.info("[SHUTDOWN] MCU reset to idle state")
    except Exception as e:
        logger.error(f"[SHUTDOWN] Error resetting MCU: {e}")
    logger.info("[SHUTDOWN] Cleanup complete — exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _shutdown_handler)
signal.signal(signal.SIGINT, _shutdown_handler)


# ── Start ──

boot_total = time.time() - BOOT_START
logger.info(f"Total boot time: {boot_total:.2f}s")
if mpu_detector and mpu_detector.available:
    logger.info(f"On-device AI: READY ({mpu_detector.status_detail})")
else:
    logger.info("On-device AI: browser-only mode (no model/runtime)")
logger.info("Starting WebUI brick — waiting for browser connections...")
logger.info("")
try:
    App.run()
except KeyboardInterrupt:
    logger.info("[SHUTDOWN] KeyboardInterrupt — shutting down")
    _shutdown_handler(signal.SIGINT, None)
except Exception as e:
    logger.error(f"[FATAL] App.run() raised: {e}")
    _shutdown_handler(signal.SIGTERM, None)
