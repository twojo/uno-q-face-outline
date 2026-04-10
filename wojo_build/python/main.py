# SPDX-FileCopyrightText: Copyright (C) 2025 ARDUINO SA <http://www.arduino.cc>
#
# SPDX-License-Identifier: MPL-2.0
#
# Uno Q Face Outline Tracker Demo — main.py
# Based on Leonardo Cavagnis' Greetings demo with robust face mesh tracking.
#
# Architecture:
#   Browser (MediaPipe 478-pt face mesh via webcam)
#     -> socket.io "face_data" {faces, expression, landmarks...}
#     -> this script (orchestrator)
#     -> Bridge RPC -> MCU (LED matrix, RGB LED, servo)
#
#   VideoObjectDetection brick acts as fallback when the browser
#   hasn't sent face_data for BROWSER_IDLE_TIMEOUT seconds.

from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.video_objectdetection import VideoObjectDetection
from datetime import datetime, UTC
import time
import threading

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONFIDENCE_DEFAULT = 0.5
DEBOUNCE_SEC = 5.0
BROWSER_IDLE_TIMEOUT = 10.0
GREET_COOLDOWN = 8.0
EXPRESSION_COOLDOWN = 3.0
STATUS_INTERVAL = 30.0

# ---------------------------------------------------------------------------
# Brick initialisation (same as Leonardo's original)
# ---------------------------------------------------------------------------

ui = WebUI()
detection_stream = VideoObjectDetection(
    confidence=CONFIDENCE_DEFAULT, debounce_sec=DEBOUNCE_SEC
)

# ---------------------------------------------------------------------------
# State tracking
# ---------------------------------------------------------------------------

_state_lock = threading.Lock()
_state = {
    "threshold_ready": False,
    "last_browser_ts": 0.0,
    "last_greet_ts": 0.0,
    "last_expression_ts": 0.0,
    "last_expression": "neutral",
    "face_count": 0,
    "faces_present": False,
    "total_detections": 0,
    "browser_connected": False,
    "boot_time": time.monotonic(),
}


def _now():
    return time.monotonic()


def _log(tag, msg):
    ts = datetime.now(UTC).strftime("%H:%M:%S")
    print(f"[{ts}] [{tag}] {msg}")


# ---------------------------------------------------------------------------
# Confidence threshold (robust version of Leonardo's override_th handler)
# ---------------------------------------------------------------------------

def safe_override_threshold(sid, threshold):
    with _state_lock:
        try:
            val = float(threshold)
            val = max(0.0, min(1.0, val))
        except (TypeError, ValueError):
            _log("THRESH", f"Invalid threshold value: {threshold}")
            return

        try:
            detection_stream.override_threshold(val)
            _state["threshold_ready"] = True
        except AttributeError:
            if _state["threshold_ready"]:
                _log("THRESH", f"override_threshold failed for {val}")
            else:
                _log("THRESH", "Model not ready yet, threshold override deferred")


ui.on_message("override_th", safe_override_threshold)

# ---------------------------------------------------------------------------
# Bridge helpers — safe wrappers for MCU calls
# ---------------------------------------------------------------------------

def _bridge_call(provider, *args):
    try:
        Bridge.call(provider, *args)
    except Exception as e:
        _log("BRIDGE", f"Bridge.call('{provider}') failed: {e}")


def _greet_if_ready():
    now = _now()
    with _state_lock:
        if now - _state["last_greet_ts"] < GREET_COOLDOWN:
            return False
        _state["last_greet_ts"] = now
    _bridge_call("greet")
    _log("GREET", "Servo greeting triggered")
    return True


def _send_expression(expr):
    now = _now()
    with _state_lock:
        if expr == _state["last_expression"]:
            if now - _state["last_expression_ts"] < EXPRESSION_COOLDOWN:
                return
        _state["last_expression"] = expr
        _state["last_expression_ts"] = now

    if expr == "surprised":
        _greet_if_ready()
        _log("EXPR", "Surprise detected — greeting")
    elif expr == "happy":
        _log("EXPR", "Smile detected")
    elif expr == "angry":
        _log("EXPR", "Brow raise detected")


# ---------------------------------------------------------------------------
# Face state transitions
# ---------------------------------------------------------------------------

def _on_faces_appear(count, source):
    with _state_lock:
        was_present = _state["faces_present"]
        _state["faces_present"] = True
        _state["face_count"] = count
        _state["total_detections"] += 1

    if not was_present:
        _log("FACE", f"{count} face(s) appeared [{source}]")
        _greet_if_ready()

    ui.send_message("face_status", message={
        "faces": count,
        "source": source,
        "timestamp": datetime.now(UTC).isoformat(),
    })


def _on_faces_disappear(source):
    with _state_lock:
        was_present = _state["faces_present"]
        _state["faces_present"] = False
        _state["face_count"] = 0

    if was_present:
        _log("FACE", f"All faces gone [{source}]")


# ---------------------------------------------------------------------------
# Browser face mesh data handler (the Wojo addition)
#
# The browser's app.js emits:
#   socket.emit('face_data', {faces: <int>, expression: <str>})
# after each MediaPipe detectForVideo() frame.
# ---------------------------------------------------------------------------

def handle_face_data(sid, data):
    if not isinstance(data, dict):
        return

    with _state_lock:
        _state["last_browser_ts"] = _now()
        _state["browser_connected"] = True

    face_count = 0
    try:
        face_count = int(data.get("faces", 0))
    except (TypeError, ValueError):
        pass

    if face_count > 0:
        _on_faces_appear(face_count, "mesh")
    else:
        _on_faces_disappear("mesh")

    expression = data.get("expression", "neutral")
    if isinstance(expression, str) and expression != "neutral":
        _send_expression(expression)

    ui.send_message("detection", message={
        "content": f"face (mesh x{face_count})" if face_count > 0 else "no face",
        "confidence": 1.0 if face_count > 0 else 0.0,
        "timestamp": datetime.now(UTC).isoformat(),
        "source": "mediapipe",
        "expression": expression,
        "face_count": face_count,
    })


ui.on_message("face_data", handle_face_data)

# ---------------------------------------------------------------------------
# VideoObjectDetection brick callbacks (Leonardo's original, enhanced)
#
# These fire from the SDK's built-in YuNet model when the camera brick
# detects faces.  They act as the FALLBACK source — only trigger the
# greeting when the browser hasn't been sending mesh data recently.
# ---------------------------------------------------------------------------

def _browser_is_active():
    with _state_lock:
        return (_now() - _state["last_browser_ts"]) < BROWSER_IDLE_TIMEOUT


def face_detected_brick():
    if _browser_is_active():
        return

    _on_faces_appear(1, "brick")
    _log("BRICK", "Face detected via VideoObjectDetection (fallback)")


detection_stream.on_detect("face", face_detected_brick)


def send_detections_to_ui(detections: dict):
    if _browser_is_active():
        return

    for key, value in detections.items():
        entry = {
            "content": key,
            "confidence": value,
            "timestamp": datetime.now(UTC).isoformat(),
            "source": "brick",
        }
        ui.send_message("detection", message=entry)


detection_stream.on_detect_all(send_detections_to_ui)

# ---------------------------------------------------------------------------
# Status heartbeat — periodic log of system health
# ---------------------------------------------------------------------------

def _status_loop():
    while True:
        time.sleep(STATUS_INTERVAL)
        with _state_lock:
            uptime = int(_now() - _state["boot_time"])
            total = _state["total_detections"]
            browser = _state["browser_connected"]
            faces = _state["face_count"]
            expr = _state["last_expression"]
        mins, secs = divmod(uptime, 60)
        _log("STATUS",
             f"up {mins}m{secs}s | detections={total} | "
             f"browser={'yes' if browser else 'no'} | "
             f"faces={faces} | expr={expr}")


_status_thread = threading.Thread(target=_status_loop, daemon=True)
_status_thread.start()

# ---------------------------------------------------------------------------
# Boot
# ---------------------------------------------------------------------------

_log("BOOT", "Uno Q Face Outline Tracker starting")
_log("BOOT", f"Confidence={CONFIDENCE_DEFAULT}, Debounce={DEBOUNCE_SEC}s, "
             f"Browser idle timeout={BROWSER_IDLE_TIMEOUT}s")
_log("BOOT", "Waiting for browser face mesh or brick fallback...")

App.run()
