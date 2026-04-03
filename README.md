# Wojo's Uno Q Face Outline Demo

Real-time face tracking demo for the **Arduino Uno Q** (Qualcomm QRB2210) built with the **Arduino App Lab** and **Bricks SDK**.

Uses Google MediaPipe Face Landmarker (478 landmarks, up to 4 faces) running entirely in the browser — zero cloud dependency for inference.

## Features

- **Face Mesh & Outline** — real-time 478-point landmark overlay with configurable mesh, contour, iris, and oval rendering
- **Expression Emojis** — detects smile, surprise, eyebrow raise, and maps to emoji overlay
- **Blink Detection** — real-time blink counter with EAR (Eye Aspect Ratio) algorithm
- **Pupil Diameter** — iris circle overlay with estimated diameter in mm (Ventuno mode)
- **Head Pose** — yaw/pitch estimation from landmark geometry
- **Device Simulation** — toggle between Uno Q (throttled: 2 faces, frame skip) and Ventuno (full speed: 4 faces, pupil measurement)
- **Bridge Integration** — MCU ↔ MPU communication via Arduino Router Bridge RPC

## Architecture

```
┌─────────────────────────────────────────────┐
│  Browser (WebUI Brick)                      │
│  assets/index.html                          │
│  ├─ MediaPipe Face Landmarker (WASM)        │
│  ├─ Canvas overlay (mesh/outline/iris/HUD)  │
│  └─ WebSocket ↔ python/main.py             │
├─────────────────────────────────────────────┤
│  Linux MPU — Qualcomm QRB2210               │
│  python/main.py                             │
│  ├─ WebUI Brick (serves frontend + WS)      │
│  ├─ Bridge RPC → MCU                        │
│  └─ Face state tracking & forwarding        │
├─────────────────────────────────────────────┤
│  STM32 MCU — STM32U585                      │
│  sketch/sketch.ino                          │
│  ├─ Bridge RPC handlers                     │
│  ├─ Status LED (face present indicator)     │
│  └─ Ambient sensor reads → MPU              │
└─────────────────────────────────────────────┘
```

## Project Structure

```
├── app.yaml                 # App Lab config — bricks, board, metadata
├── python/
│   └── main.py              # MPU entry — WebUI Brick + Bridge RPC
├── sketch/
│   ├── sketch.ino           # MCU entry — Bridge handlers + sensors
│   └── sketch.yaml          # Arduino CLI board & library config
├── assets/
│   ├── index.html           # Full face tracking frontend (self-contained)
│   └── qualcomm-logo.png    # Qualcomm branding asset
└── README.md
```

## Hardware Requirements

| Component | Details |
|-----------|---------|
| **Board** | Arduino Uno Q (QRB2210 + STM32U585) |
| **Camera** | Standard UVC USB webcam |
| **Connection** | USB-C hub/dongle |
| **Browser** | Chrome/Edge on same network |

## Installation

### Option A: Arduino App Lab Import (Recommended)

1. Download this repository as a `.zip`
2. Open [Arduino App Lab](https://lab.arduino.cc)
3. Click **Import App** → select the `.zip`
4. App Lab auto-detects `app.yaml` and wires everything up
5. Deploy to your connected Uno Q

### Option B: Manual Setup

1. Clone this repo to your Uno Q workspace
2. Ensure the Bricks SDK is installed (`arduino:web_ui`)
3. Flash `sketch/sketch.ino` to the STM32 MCU via App Lab
4. Run `python/main.py` on the Linux MPU container
5. Open the WebUI URL shown in the terminal

## Bridge RPC Reference

### MPU → MCU (Python calls sketch)

| Function | Payload | Purpose |
|----------|---------|---------|
| `face_detected` | `{"count": N, "expr": "smile"}` | Faces visible in camera |
| `no_face` | — | No faces detected |
| `set_device_mode` | `"uno_q"` or `"ventuno"` | Device simulation toggle |

### MCU → MPU (sketch calls Python)

| Function | Payload | Purpose |
|----------|---------|---------|
| `mcu_ready` | — | MCU initialization complete |
| `sensor_data` | `{"light": N, "mode": "...", "face": bool}` | Periodic sensor readings |

## WebSocket Events (Browser ↔ MPU)

| Event | Direction | Payload |
|-------|-----------|---------|
| `face_data` | Browser → MPU | Face telemetry JSON (faces, blinks, expression, pupils, pose) |
| `device_switch` | Browser → MPU | `{"device": "uno_q"}` or `{"device": "ventuno"}` |
| `capture_snapshot` | Browser → MPU | Snapshot request |
| `state_update` | MPU → Browser | Full face state JSON |
| `sensor_update` | MPU → Browser | MCU sensor readings |
| `snapshot_ack` | MPU → Browser | `{"status": "ok", "timestamp": "..."}` |

## Delegate Note

> **CPU delegate must be used first.** The Adreno 650 GPU delegate causes incorrect inference results despite WebGL working. MediaPipe defaults to CPU (WASM) which provides correct landmark positions.

## Credits

- [Arduino App Lab](https://docs.arduino.cc/software/app-lab/)
- [Arduino App Bricks](https://github.com/arduino/app-bricks-py)
- [Google MediaPipe](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker)
- Qualcomm QRB2210 Dragonwing SoC
