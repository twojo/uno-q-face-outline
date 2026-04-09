# SPDX-FileCopyrightText: Copyright (C) 2025 Wojo
#
# SPDX-License-Identifier: MIT
#
# Wojo's Face Outline Demo — App Lab Coordinator
# Arduino Uno Q (Qualcomm QRB2210 MPU + STM32U585 MCU)
#
# This script runs on the QRB2210's Debian Linux and coordinates:
#   - VideoObjectDetection brick: face detection via USB camera
#   - WebUI brick: serves the browser UI + Socket.IO messaging
#   - Bridge RPC: forwards face state to the STM32 MCU for LED/RGB feedback
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
detection_stream = VideoObjectDetection(confidence=0.5, debounce_sec=0.0)

ui.on_message("override_th", lambda sid, threshold: detection_stream.override_threshold(threshold))

_start_time = time.monotonic()
_face_present = False
_total_detections = 0
_last_log_time = 0
_LOG_INTERVAL = 5.0

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

def face_detected():
    global _face_present
    if not _face_present:
        _face_present = True
        safe_call("show_face")
        safe_call("flash_face", "3")
        safe_call("set_rgb", "green")
        _log("FACE APPEARED")

detection_stream.on_detect("face", face_detected)

_heartbeat_count = 0

def send_detections_to_ui(detections: dict):
    global _face_present, _heartbeat_count, _total_detections, _last_log_time
    n = len(detections)
    _heartbeat_count += 1
    _total_detections += n

    if n == 0 and _face_present:
        _face_present = False
        safe_call("set_rgb", "off")
        safe_call("show_no_face")
        _log("FACE LOST")
    elif n > 0 and _heartbeat_count % 30 == 0:
        safe_call("show_face")

    now = time.monotonic()
    if now - _last_log_time >= _LOG_INTERVAL:
        _last_log_time = now
        state = "tracking" if _face_present else "idle"
        _log(f"status={state}  faces={n}  total_detections={_total_detections}  heartbeats={_heartbeat_count}")

    ui.send_message("face_count", {"count": n})

    for key, value in detections.items():
        conf = value.get("confidence") if isinstance(value, dict) else value
        entry = {
            "content": key,
            "confidence": conf,
            "timestamp": datetime.now(UTC).isoformat()
        }
        ui.send_message("detection", entry)

detection_stream.on_detect_all(send_detections_to_ui)

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
