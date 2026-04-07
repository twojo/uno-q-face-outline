# Wojo's Uno Q Face Outline Demo — MPU Entry Point
#
# This script runs on the Linux side (Qualcomm QRB2210) and acts as
# the coordinator between three systems:
#
#   Browser (MediaPipe)  <--WebSocket-->  MPU (this script)  <--Bridge-->  MCU (sketch.ino)
#
# The WebUI brick automatically serves everything in the assets/
# directory. The browser runs face tracking locally using MediaPipe
# WASM and sends detection results back here over WebSocket. This
# script then translates those results into Bridge calls that drive
# the LED matrix on the MCU.
#
# Dependencies: only stdlib + App Lab SDK. No pip packages needed.

from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
import json
import socket
import time
import threading

logger = Logger("face-demo")
ui = WebUI()

# Shared state that tracks what the browser is currently seeing.
# Updated on every face_data WebSocket message from the frontend.
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

# Tracks whether a face was visible on the previous update so we
# can detect transitions (no face -> face, face -> no face).
last_face_present = False


def get_ip_address():
    """Return the device's primary LAN IP by briefly opening a UDP
    socket to a public DNS server. No data is actually sent."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "No IP"


def startup_sequence():
    """Runs once at boot in a background thread. Waits briefly for the
    MCU Bridge to come up, then scrolls the IP address across the LED
    matrix so the user knows where to point their browser."""
    time.sleep(2)
    ip = get_ip_address()
    logger.info(f"Device IP: {ip}")
    Bridge.call("scroll_text", f"  IP: {ip}  ")
    time.sleep(8)
    Bridge.call("scroll_text", "  Face Demo Ready  ")

startup_thread = threading.Thread(target=startup_sequence, daemon=True)
startup_thread.start()


# --- Bridge provider (MCU -> MPU) ---

def on_mcu_ready():
    """Called by the MCU sketch after Bridge.begin() completes on
    the STM32 side. Useful for confirming the two processors are
    communicating."""
    logger.info("MCU ready — Bridge link confirmed")

Bridge.provide("mcu_ready", on_mcu_ready)


# --- WebSocket handlers (Browser -> MPU) ---

def on_browser_connect(sid):
    """Push the current face state to a newly connected browser so
    its UI starts in sync with reality."""
    logger.info(f"Browser connected: {sid}")
    ui.send_message("state_update", json.dumps(face_state))

ui.on_connect(on_browser_connect)


def on_face_data(sid, data):
    """Handle face tracking telemetry from the browser. The frontend
    sends a compact JSON payload roughly every 500ms containing face
    count, blink count, dominant expression, pupil diameters, and
    head pose angles.

    State transitions drive LED matrix updates:
      - No face -> face: flash the smiley 3x, then hold it
      - Face present:    show expression bitmap or default smiley
      - Face -> no face: show the X pattern
    """
    global last_face_present
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

        if face_now and not last_face_present:
            Bridge.call("flash_face", 3)
            expr = face_state["expression"]
            if expr != "neutral":
                time.sleep(0.5)
                Bridge.call("show_expression", expr)

        elif face_now:
            expr = face_state["expression"]
            if expr != "neutral":
                Bridge.call("show_expression", expr)
            else:
                Bridge.call("show_face")

        elif not face_now and last_face_present:
            Bridge.call("show_no_face")

        last_face_present = face_now

    except Exception as e:
        logger.error(f"face_data error: {e}")

ui.on_message("face_data", on_face_data)


def on_device_switch(sid, data):
    """Handle device profile toggle from the frontend UI. Forwards the
    mode name to the MCU so it can scroll a confirmation message."""
    try:
        payload = json.loads(data) if isinstance(data, str) else data
        mode = payload.get("device", "uno_q")
        face_state["device_mode"] = mode
        logger.info(f"Device mode: {mode}")
        Bridge.call("set_device_mode", mode)
    except Exception as e:
        logger.error(f"device_switch error: {e}")

ui.on_message("device_switch", on_device_switch)


def on_capture_snapshot(sid, data):
    """Acknowledge a snapshot request from the frontend."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    logger.info(f"Snapshot captured at {timestamp}")
    ui.send_message("snapshot_ack", json.dumps({
        "status": "ok",
        "timestamp": timestamp
    }))

ui.on_message("capture_snapshot", on_capture_snapshot)


# --- Start ---

logger.info("Wojo's Uno Q Face Outline Demo — starting")
App.run()
