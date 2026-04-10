# SPDX-FileCopyrightText: Copyright (C) 2025 ARDUINO SA <http://www.arduino.cc>
#
# SPDX-License-Identifier: MPL-2.0

from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.video_objectdetection import VideoObjectDetection
from datetime import datetime, UTC
import time

ui = WebUI()
detection_stream = VideoObjectDetection(confidence=0.5, debounce_sec=5.0)

_threshold_ready = False

def safe_override_threshold(sid, threshold):
    global _threshold_ready
    try:
        detection_stream.override_threshold(threshold)
        _threshold_ready = True
    except AttributeError:
        if _threshold_ready:
            print(f"WARNING: override_threshold failed unexpectedly for value {threshold}")
        else:
            print("INFO: Model not ready yet, threshold override deferred")

ui.on_message("override_th", safe_override_threshold)

# Example usage: Register a callback for when a specific object is detected
def face_detected():
  Bridge.call("greet")
  print("Face detected!")

detection_stream.on_detect("face", face_detected)

# Example usage: Register a callback for when all objects are detected
def send_detections_to_ui(detections: dict):
  for key, value in detections.items():
    entry = {
      "content": key,
      "confidence": value,
      "timestamp": datetime.now(UTC).isoformat()
    }    
    ui.send_message("detection", message=entry)

detection_stream.on_detect_all(send_detections_to_ui)

App.run()
