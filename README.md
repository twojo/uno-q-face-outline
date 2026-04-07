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

### Bridge Registration

**MCU side** (`sketch.ino` → `setup()`): All MCU functions are registered with `Bridge.provide("name", handler)`, making them callable from Python. The `loop()` is empty — the sketch is entirely event-driven via Bridge callbacks.

**MPU side** (`python/main.py`): Python-side providers use `Bridge.provide("name", handler)` to expose functions the MCU can call. WebSocket handlers use `ui.on_message("event", handler)` (function-call registration, not decorators).

## WebSocket Events (Browser ↔ MPU)

| Event | Direction | Payload |
|-------|-----------|---------|
| `face_data` | Browser → MPU | `{faces, blinks, expression, pupilL, pupilR, yaw, pitch}` |
| `device_switch` | Browser → MPU | `{"device": "uno_q"}` or `{"device": "ventuno"}` |
| `capture_snapshot` | Browser → MPU | Snapshot request |
| `state_update` | MPU → Browser | Full face state JSON |
| `snapshot_ack` | MPU → Browser | `{"status": "ok", "timestamp": "..."}` |

## Dependencies

This project is designed to pull as few external resources as possible.

### MCU (sketch.ino) — Arduino Libraries

| Library | Version | Notes |
|---------|---------|-------|
| `Arduino_RouterBridge` | 0.3.0 | Bridge RPC — the only library listed in sketch.yaml |
| `Arduino_RPClite` | 0.2.1 | Transitive dep of RouterBridge |
| `ArxContainer` | 0.7.0 | Transitive dep of RouterBridge |
| `ArxTypeTraits` | 0.3.2 | Transitive dep of RouterBridge |
| `DebugLog` | 0.8.4 | Transitive dep of RouterBridge |
| `MsgPack` | 0.4.2 | Transitive dep of RouterBridge |
| `Arduino_LED_Matrix` | (platform) | Bundled with arduino:zephyr, not in sketch.yaml |
| `ArduinoGraphics` | (platform) | Bundled with arduino:zephyr, not in sketch.yaml |

### MPU (python/main.py) — Python

Only the App Lab SDK (`arduino.app_utils`, `arduino.app_bricks.web_ui`) and Python stdlib. **Zero pip packages.**

### Browser (assets/index.html) — CDN Resources

| Resource | CDN | Pinned | Required |
|----------|-----|--------|----------|
| `@mediapipe/tasks-vision` | jsdelivr | 0.10.3 | Yes — core face tracking engine |
| `face_landmarker.task` model | Google Cloud Storage | float16/1 | Yes — trained model weights (~4MB, cached) |
| Google Fonts (Inter, JetBrains Mono) | Google Fonts | latest | No — degrades to system fonts if offline |

### Replit Preview Only (app.py)

| Package | Notes |
|---------|-------|
| `flask` | Serves the HTML for Replit's web preview |
| `psutil` | System stats overlay — stable, no version sensitivity |

Both are excluded from the App Lab project via `.gitignore`.

## Delegate Selection & Landmark Validation

The Qualcomm QRB2210 includes an Adreno 650 GPU that supports WebGL — but GPU-accelerated inference through MediaPipe's GPU delegate produces **incorrect landmark positions** despite appearing to work. The landmarks have the right count (478) but are spatially wrong (collapsed, inverted, or drifted).

### Strategy: CPU-First with Runtime Self-Check

The app uses a **CPU-first** delegate strategy with automatic runtime validation:

1. **Try CPU delegate first** — WASM-based inference is slower but always correct
2. **Fall back to GPU** only if CPU fails to load
3. **Validate the first 5 frames** of landmarks with geometric sanity checks
4. **Auto-switch** if validation fails (GPU→CPU or CPU→GPU)
5. **Continuous monitoring** every 60 seconds to detect degradation

### Delegate State Machine

```
                         ┌──────────┐
                         │ UNTESTED │
                         └────┬─────┘
                              │ first face detected
                              v
                        ┌───────────┐
                   ┌───>│VALIDATING │<───────────────────┐
                   │    └─────┬─────┘                    │
                   │          │ 5 frames checked         │
                   │    ┌─────┴──────┐                   │
                   │    │            │                    │
                   │  >=3 pass    >=3 fail               │
                   │    │            │                    │
                   │    v            v                    │
                   │ ┌──────┐  ┌────────┐                │
                   │ │PASSED│  │ FAILED │                │
                   │ └──┬───┘  └───┬────┘                │
                   │    │          │ auto-switch          │
                   │    │          v                      │
                   │    │    ┌───────────┐  reload        │
                   │    │    │RECOVERING │──delegate──────┘
                   │    │    └───────────┘
                   │    │
                   │    │ continuous check (60s)
                   │    v
                   │ ┌────────┐
                   │ │DEGRADED│ (warn, no auto-switch)
                   │ └────────┘
                   └───────────────────── (manual retry)
```

### Landmark Sanity Checks (6 tests per frame)

| # | Check | What it catches |
|---|-------|-----------------|
| 1 | Landmark count = 478 | Incomplete model load or corrupt output |
| 2 | Bounding box span > 3% of frame | All landmarks collapsed to one point |
| 3 | Out-of-bounds < 20 landmarks | Landmarks flying off-screen |
| 4 | Nose tip near face center | Facial geometry scrambled |
| 5 | Eye separation 2-50% of frame | Eyes overlapping or impossibly far |
| 6 | Forehead above chin | Y-axis inverted inference |

### Diagnostics

The hidden diagnostics panel (toggle via title bar) shows real-time status:
- **Landmark Sanity** row — current state (UNTESTED → VALIDATING → PASSED/FAILED)
- **Face Landmarker Model** row — which delegate loaded and any reload events
- Console logs prefixed with `[SANITY]` for detailed frame-by-frame validation

## Credits

- [Arduino App Lab](https://docs.arduino.cc/software/app-lab/)
- [Arduino App Bricks](https://github.com/arduino/app-bricks-py)
- [Arduino App Bricks Examples](https://github.com/arduino/app-bricks-examples)
- [Google MediaPipe](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker)
- Qualcomm QRB2210 Dragonwing SoC
