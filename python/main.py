# SPDX-FileCopyrightText: Copyright (C) 2025 Wojo
#
# SPDX-License-Identifier: MIT

from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.video_objectdetection import VideoObjectDetection
from datetime import datetime, UTC
import socket
import threading
import time

ui = WebUI()
detection_stream = VideoObjectDetection(confidence=0.5, debounce_sec=0.0)

ui.on_message("override_th", lambda sid, threshold: detection_stream.override_threshold(threshold))

face_present = False

def safe_call(cmd, arg=""):
    try:
        Bridge.call(cmd, arg)
    except Exception:
        pass

def face_detected():
    global face_present
    if not face_present:
        face_present = True
        safe_call("show_face")
        safe_call("flash_face", "3")
        safe_call("set_rgb", "green")
    print("Face detected!")

detection_stream.on_detect("face", face_detected)

_heartbeat_count = 0

def send_detections_to_ui(detections: dict):
    global face_present, _heartbeat_count
    n = len(detections)
    _heartbeat_count += 1

    if n == 0 and face_present:
        face_present = False
        safe_call("set_rgb", "off")
        safe_call("show_no_face")
    elif n > 0 and _heartbeat_count % 30 == 0:
        safe_call("show_face")

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
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        safe_call("scroll_text", f"  {ip}  ")
        safe_call("scroll_text", f"  {ip}  ")
    except Exception:
        pass
    safe_call("scroll_text", "  READY  ")

threading.Thread(target=startup, daemon=True).start()

App.run()
