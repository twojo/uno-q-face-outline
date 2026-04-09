# SPDX-FileCopyrightText: Copyright (C) 2025 Wojo
#
# SPDX-License-Identifier: MIT
#
# Wojo's Face Outline Demo — App Lab Coordinator
# Arduino Uno Q (Qualcomm QRB2210 MPU + STM32U585 MCU)
#
# This script runs on the QRB2210's Debian Linux and coordinates:
#   - WebUI brick: serves the browser UI + Socket.IO messaging
#   - Bridge RPC: forwards face state from browser to MCU for LED/RGB feedback
#   - VideoObjectDetection brick: backup on-device detection
#
# The browser runs MediaPipe Face Landmarker (WASM) and sends face data
# via Socket.IO. This script forwards expression/state changes to the MCU
# through Bridge RPC.
#
# Runs inside Arduino App Lab. For standalone (no App Lab) use:
#   python3 direct/face_tracker.py

from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.video_objectdetection import VideoObjectDetection
from datetime import datetime, UTC
import socket
import threading
import time
import os

ui = WebUI()
detection_stream = VideoObjectDetection(confidence=0.5, debounce_sec=1.0)

_start_time = time.monotonic()
_face_present = False
_total_detections = 0
_last_log_time = 0
_last_expression = ""
_last_browser_msg = 0
_LOG_INTERVAL = 5.0
_BROWSER_TIMEOUT = 10.0

EXPRESSION_TO_MCU = {
    "happy": "smile",
    "surprised": "surprise",
    "angry": "eyebrow",
    "sad": "eyebrow",
    "neutral": "neutral",
}

def _uptime():
    s = int(time.monotonic() - _start_time)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"

def _ts():
    return datetime.now(UTC).strftime("%H:%M:%S")

def _log(msg):
    print(f"[{_ts()}] uptime={_uptime()}  {msg}", flush=True)

def safe_call(cmd, arg=""):
    try:
        Bridge.call(cmd, arg)
    except Exception:
        pass

def on_face_data(sid, data):
    global _face_present, _total_detections, _last_log_time, _last_expression, _last_browser_msg

    if not isinstance(data, dict):
        return

    _last_browser_msg = time.monotonic()

    n = data.get("faces", 0)
    expr = data.get("expression", "")
    yaw = data.get("yaw", 0)
    pitch = data.get("pitch", 0)

    if n > 0:
        _total_detections += 1

        if not _face_present:
            _face_present = True
            safe_call("show_face")
            safe_call("flash_face", "3")
            safe_call("set_rgb", "green")
            _log(f"FACE APPEARED  expr={expr}")

        mcu_expr = EXPRESSION_TO_MCU.get(expr, "neutral")
        if mcu_expr != _last_expression:
            _last_expression = mcu_expr
            safe_call("show_expression", mcu_expr)
            _log(f"EXPRESSION  {expr} -> mcu:{mcu_expr}")

    elif n == 0 and _face_present:
        _face_present = False
        _last_expression = ""
        safe_call("set_rgb", "red")
        safe_call("show_no_face")
        _log("FACE LOST")

    now = time.monotonic()
    if now - _last_log_time >= _LOG_INTERVAL:
        _last_log_time = now
        state = "tracking" if _face_present else "idle"
        _log(f"status={state}  faces={n}  expr={expr}  yaw={yaw:.1f}  pitch={pitch:.1f}  total={_total_detections}")

ui.on_message("face_data", on_face_data)

def on_expression_change(sid, data):
    if not isinstance(data, dict):
        return
    expr = data.get("expression", "")
    mcu_expr = EXPRESSION_TO_MCU.get(expr, "neutral")
    safe_call("show_expression", mcu_expr)

ui.on_message("expression_change", on_expression_change)
ui.on_message("override_th", lambda sid, threshold: detection_stream.override_threshold(threshold))

def on_brick_detect(detections: dict):
    global _face_present
    if time.monotonic() - _last_browser_msg < _BROWSER_TIMEOUT:
        return

    n = len(detections)

    if n > 0 and not _face_present:
        _face_present = True
        safe_call("show_face")
        safe_call("set_rgb", "green")
        _log(f"FACE APPEARED (brick fallback)  count={n}")

    elif n == 0 and _face_present:
        _face_present = False
        safe_call("show_no_face")
        safe_call("set_rgb", "red")
        _log("FACE LOST (brick fallback)")

    ui.send_message("face_count", {"count": n})

detection_stream.on_detect_all(on_brick_detect)

def startup():
    time.sleep(3)
    ip = "unknown"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        safe_call("scroll_text", f"  {ip}  ")
        safe_call("scroll_text", f"  {ip}  ")
    except Exception:
        pass

    _log(f"READY  ip={ip}  pid={os.getpid()}")
    safe_call("scroll_text", "  READY  ")

threading.Thread(target=startup, daemon=True).start()

_log(f"BOOT  pid={os.getpid()}")
App.run()
