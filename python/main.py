"""
Wojo's Uno Q Face Outline Demo — Arduino App Lab MPU Entry Point

Runs on the Linux MPU (Qualcomm QRB2210) container.
Uses the WebUI Brick to serve the face-tracking frontend and
the Bridge to communicate with the STM32 MCU sketch.

Bricks used:
  - arduino:web_ui   → serves assets/index.html, WebSocket messaging
  - Bridge           → RPC calls to/from the MCU (sketch.ino)
"""

from arduino.app_utils import App, Bridge
from arduino.app_bricks.web_ui import WebUI
import json
import time

app = App()
ui = WebUI()
bridge = Bridge()

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

# ── WebSocket Handlers ────────────────────────────────────────────

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
    try:
        payload = json.loads(data) if isinstance(data, str) else data

        FACE_STATE["faces_detected"] = payload.get("faces", 0)
        FACE_STATE["blink_count"] = payload.get("blinks", 0)
        FACE_STATE["expression"] = payload.get("expression", "neutral")
        FACE_STATE["pupil_l_mm"] = payload.get("pupilL", 0.0)
        FACE_STATE["pupil_r_mm"] = payload.get("pupilR", 0.0)
        FACE_STATE["yaw"] = payload.get("yaw", 0.0)
        FACE_STATE["pitch"] = payload.get("pitch", 0.0)

        if FACE_STATE["faces_detected"] > 0:
            bridge.call("face_detected", json.dumps({
                "count": FACE_STATE["faces_detected"],
                "expr": FACE_STATE["expression"]
            }))
        else:
            bridge.call("no_face")

    except Exception as e:
        print(f"[WebUI] face_data error: {e}")

@ui.on_message("device_switch")
def on_device_switch(sid, data):
    """
    User toggled between Uno Q and Ventuno in the frontend.
    Forward the mode to the MCU so it can adjust LED/sensor behavior.
    """
    try:
        payload = json.loads(data) if isinstance(data, str) else data
        mode = payload.get("device", "uno_q")
        FACE_STATE["device_mode"] = mode
        print(f"[WebUI] Device mode switched to: {mode}")
        bridge.call("set_device_mode", mode)
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

# ── Bridge callbacks (MCU → MPU) ─────────────────────────────────

@bridge.on("mcu_ready")
def on_mcu_ready():
    """MCU finished initialization and is ready for RPC calls."""
    print("[Bridge] MCU reports ready")

@bridge.on("sensor_data")
def on_sensor_data(data):
    """
    MCU sends ambient sensor readings (light, proximity, IMU).
    Forward to any connected browser clients.
    """
    ui.send_message("sensor_update", data)

# ── Serve the WebUI ───────────────────────────────────────────────

ui.serve("./assets/index.html")

print("[App] Wojo's Uno Q Face Outline Demo — starting")
print("[App] WebUI served from ./assets/index.html")
print("[App] Waiting for browser connection...")

App.run()
