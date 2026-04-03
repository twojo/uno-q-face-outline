"""
Wojo's Uno Q Face Outline Demo — Arduino App Lab MPU Entry Point

Runs on the Linux MPU (Qualcomm QRB2210) container.
Uses the WebUI Brick to serve the face-tracking frontend and
the Bridge to communicate with the STM32 MCU sketch.

Bricks used:
  - arduino:web_ui   → serves assets/index.html, WebSocket messaging
  - Bridge           → RPC calls to/from the MCU (sketch.ino)

On boot:
  1. Gets the device IP address
  2. Scrolls the IP on the 12x8 LED matrix via Bridge
  3. Serves the WebUI frontend
  4. Listens for face telemetry from the browser
  5. Forwards face state to MCU for LED matrix display
"""

from arduino.app_utils import *
from arduino.app_bricks.web_ui import WebUI
import json
import socket
import time
import threading

ui = WebUI()

FACE_STATE = {
    "faces_detected": 0,
    "blink_count": 0,
    "expression": "neutral",
    "pupil_l_mm": 0.0,
    "pupil_r_mm": 0.0,
    "yaw": 0.0,
    "pitch": 0.0,
    "device_mode": "uno_q"
}

last_face_state = False

# ── Utility ──────────────────────────────────────────────────────

def get_ip_address():
    """Get the device's primary network IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "No IP"

# ── Startup: scroll IP on LED matrix ─────────────────────────────

def startup_sequence():
    """Run on boot — scroll the IP address across the LED matrix."""
    time.sleep(2)
    ip = get_ip_address()
    print(f"[App] Device IP: {ip}")
    print(f"[App] Scrolling IP on LED matrix...")
    Bridge.call("scroll_text", f"  IP: {ip}  ")
    time.sleep(8)
    Bridge.call("scroll_text", "  Face Demo Ready  ")

startup_thread = threading.Thread(target=startup_sequence, daemon=True)
startup_thread.start()

# ── WebSocket Handlers ───────────────────────────────────────────

@ui.on_connect
def on_browser_connect(sid):
    """Browser connected — push current state."""
    print(f"[WebUI] Browser connected: {sid}")
    ui.send_message("state_update", json.dumps(FACE_STATE))

@ui.on_message("face_data")
def on_face_data(sid, data):
    """
    Receive face tracking telemetry from the browser frontend.
    The frontend sends a JSON payload every 500ms with:
      { faces, blinks, expression, pupilL, pupilR, yaw, pitch }
    """
    global last_face_state
    try:
        payload = json.loads(data) if isinstance(data, str) else data

        FACE_STATE["faces_detected"] = payload.get("faces", 0)
        FACE_STATE["blink_count"] = payload.get("blinks", 0)
        FACE_STATE["expression"] = payload.get("expression", "neutral")
        FACE_STATE["pupil_l_mm"] = payload.get("pupilL", 0.0)
        FACE_STATE["pupil_r_mm"] = payload.get("pupilR", 0.0)
        FACE_STATE["yaw"] = payload.get("yaw", 0.0)
        FACE_STATE["pitch"] = payload.get("pitch", 0.0)

        face_now = FACE_STATE["faces_detected"] > 0

        if face_now and not last_face_state:
            Bridge.call("flash_face", 3)
            expr = FACE_STATE["expression"]
            if expr != "neutral":
                time.sleep(0.5)
                Bridge.call("show_expression", expr)

        elif face_now:
            expr = FACE_STATE["expression"]
            if expr != "neutral":
                Bridge.call("show_expression", expr)
            else:
                Bridge.call("show_face")

        elif not face_now and last_face_state:
            Bridge.call("show_no_face")

        last_face_state = face_now

    except Exception as e:
        print(f"[WebUI] face_data error: {e}")

@ui.on_message("device_switch")
def on_device_switch(sid, data):
    """
    User toggled between Uno Q and Ventuno in the frontend.
    Forward the mode to the MCU so it can adjust LED behavior.
    """
    try:
        payload = json.loads(data) if isinstance(data, str) else data
        mode = payload.get("device", "uno_q")
        FACE_STATE["device_mode"] = mode
        print(f"[WebUI] Device mode switched to: {mode}")
        Bridge.call("set_device_mode", mode)
    except Exception as e:
        print(f"[WebUI] device_switch error: {e}")

@ui.on_message("capture_snapshot")
def on_capture_snapshot(sid, data):
    """
    User requested a snapshot capture from the frontend.
    Acknowledge and log the event.
    """
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    print(f"[WebUI] Snapshot captured at {timestamp}")
    ui.send_message("snapshot_ack", json.dumps({
        "status": "ok",
        "timestamp": timestamp
    }))

# ── Serve the WebUI ──────────────────────────────────────────────

ui.serve("./assets/index.html")

print("[App] Wojo's Uno Q Face Outline Demo — starting")
print("[App] WebUI served from ./assets/index.html")
print("[App] Waiting for browser connection...")

App.run()
