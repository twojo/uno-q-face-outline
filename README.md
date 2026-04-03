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
- **LED Matrix Display** — built-in 12x8 LED matrix shows:
  - Device IP address scrolling on boot
  - Smiley face bitmap when a face is detected
  - Rapid flash animation on new face appearance
  - Expression-specific bitmaps (smile, surprise, eyebrow raise)
  - X pattern when no face is present
- **Bridge Integration** — MCU ↔ MPU communication via `Bridge.provide()` / `Bridge.call()` RPC

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
│  ├─ Bridge.call() → MCU functions           │
│  ├─ IP address lookup (socket)              │
│  └─ Face state tracking & forwarding        │
├─────────────────────────────────────────────┤
│  STM32 MCU — STM32U585                      │
│  sketch/sketch.ino                          │
│  ├─ Bridge.provide() RPC handlers           │
│  ├─ 12x8 LED matrix (ArduinoGraphics)       │
│  │   ├─ Scrolling text (IP, expressions)    │
│  │   ├─ Face bitmaps (smiley, surprise, X)  │
│  │   └─ Flash animation on detection        │
│  └─ Status LED (face present indicator)     │
└─────────────────────────────────────────────┘
```

## Project Structure

```
├── app.yaml                 # App Lab config — bricks, board, libraries
├── python/
│   └── main.py              # MPU entry — WebUI Brick + Bridge.call()
├── sketch/
│   ├── sketch.ino           # MCU entry — Bridge.provide() + LED matrix
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
| **LED Matrix** | Built-in 12x8 (no wiring needed) |
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
6. The LED matrix scrolls the device IP — open that address in Chrome

### Option B: Manual Setup

1. Clone this repo to your Uno Q workspace
2. Ensure the Bricks SDK is installed (`arduino:web_ui`)
3. Flash `sketch/sketch.ino` to the STM32 MCU via App Lab
4. Run `python/main.py` on the Linux MPU container
5. The LED matrix scrolls the IP — open it in your browser

## LED Matrix Behavior

| State | Display |
|-------|---------|
| **Boot** | Scrolls `"UNO"` → then `"IP: 192.168.x.x"` |
| **Waiting** | Scrolls `"Face Demo Ready"` |
| **Face detected (new)** | Rapid flash smiley 3x → hold smiley |
| **Face detected (ongoing)** | Smiley bitmap (or expression bitmap) |
| **Expression: smile** | Smiley face bitmap (mouth curve) |
| **Expression: surprise** | O-mouth + wide eyes bitmap |
| **Expression: eyebrow** | Raised eyebrows + neutral mouth |
| **No face** | X pattern |
| **Device switch** | Scrolls `"Mode: uno_q"` or `"Mode: ventuno"` |

## Bridge RPC Reference

### MPU → MCU — `Bridge.call()` (Python calls sketch)

| Function | Payload | Purpose |
|----------|---------|---------|
| `scroll_text` | `"IP: 192.168.1.42"` | Scroll any text across the 12x8 matrix |
| `show_face` | — | Display smiley face bitmap |
| `show_no_face` | — | Display X pattern (no face) |
| `flash_face` | `3` (count) | Rapidly flash face bitmap N times |
| `show_expression` | `"smile"`, `"surprise"`, `"eyebrow"` | Show expression-specific bitmap |
| `set_device_mode` | `"uno_q"` or `"ventuno"` | Switch device mode, scroll confirmation |

### MCU → MPU — `Bridge.call()` (sketch calls Python)

| Function | Payload | Purpose |
|----------|---------|---------|
| `mcu_ready` | — | MCU initialization complete |

### MCU-Side Registration — `Bridge.provide()`

All MCU functions are registered with `Bridge.provide("name", handler)` in `setup()`, making them callable from Python. The `loop()` is empty — the sketch is entirely event-driven via Bridge callbacks.

## WebSocket Events (Browser ↔ MPU)

| Event | Direction | Payload |
|-------|-----------|---------|
| `face_data` | Browser → MPU | `{faces, blinks, expression, pupilL, pupilR, yaw, pitch}` |
| `device_switch` | Browser → MPU | `{"device": "uno_q"}` or `{"device": "ventuno"}` |
| `capture_snapshot` | Browser → MPU | Snapshot request |
| `state_update` | MPU → Browser | Full face state JSON |
| `snapshot_ack` | MPU → Browser | `{"status": "ok", "timestamp": "..."}` |

## Libraries Used

| Library | Side | Purpose |
|---------|------|---------|
| `Arduino_RouterBridge` | MCU | Bridge RPC between MCU ↔ MPU |
| `Arduino_LED_Matrix` | MCU | 12x8 LED matrix control |
| `ArduinoGraphics` | MCU | Text scrolling, fonts, drawing |
| `MediaPipe Face Landmarker` | Browser | 478-point face tracking (WASM) |
| `WebUI Brick` | MPU | Serves frontend + WebSocket |

## Delegate Note

> **CPU delegate must be used first.** The Adreno 650 GPU delegate causes incorrect inference results despite WebGL working. MediaPipe defaults to CPU (WASM) which provides correct landmark positions.

## Credits

- [Arduino App Lab](https://docs.arduino.cc/software/app-lab/)
- [Arduino App Bricks](https://github.com/arduino/app-bricks-py)
- [Arduino App Bricks Examples](https://github.com/arduino/app-bricks-examples)
- [Google MediaPipe](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker)
- Qualcomm QRB2210 Dragonwing SoC
