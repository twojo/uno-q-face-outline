from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.video_objectdetection import VideoObjectDetection
from datetime import datetime, UTC
import time

ui = WebUI()
detection_stream = VideoObjectDetection(confidence=0.5, debounce_sec=5.0)

ui.on_message("override_th", lambda sid, threshold: detection_stream.override_threshold(threshold))

_face_present = False
_last_expression = ""

EXPRESSION_TO_MCU = {
    "happy": "smile",
    "surprised": "surprise",
    "angry": "eyebrow",
    "sad": "eyebrow",
    "neutral": "neutral",
}

def on_face_data(sid, data):
    global _face_present, _last_expression
    if not isinstance(data, dict):
        return

    n = data.get("faces", 0)
    expr = data.get("expression", "")

    if n > 0:
        if not _face_present:
            _face_present = True
            Bridge.call("show_face")
            Bridge.call("set_rgb", "green")

        mcu_expr = EXPRESSION_TO_MCU.get(expr, "neutral")
        if mcu_expr != _last_expression:
            _last_expression = mcu_expr
            Bridge.call("show_expression", mcu_expr)

    elif n == 0 and _face_present:
        _face_present = False
        _last_expression = ""
        Bridge.call("show_no_face")
        Bridge.call("set_rgb", "red")

ui.on_message("face_data", on_face_data)

def on_expression_change(sid, data):
    if not isinstance(data, dict):
        return
    expr = data.get("expression", "")
    mcu_expr = EXPRESSION_TO_MCU.get(expr, "neutral")
    Bridge.call("show_expression", mcu_expr)

ui.on_message("expression_change", on_expression_change)

def face_detected():
    global _face_present
    if not _face_present:
        Bridge.call("greet")
        print("Face detected!")

detection_stream.on_detect("face", face_detected)

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
