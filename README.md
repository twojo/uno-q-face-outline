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
  - `"UNO"` splash → `"BOOTING..."` → `"BRIDGE OK"` on startup
  - Device IP, RAM stats, and kernel version scrolling on boot
  - `"Face Demo Ready"` when waiting for faces
  - Smiley face bitmap when a face is detected
  - Rapid flash animation on new face appearance
  - Expression-specific bitmaps (smile, surprise, eyebrow raise)
  - Checkmark bitmap on successful boot
  - X pattern when no face is present
- **RGB LED Status** — onboard RGB LED provides at-a-glance state:
  - Red/green/blue self-test on boot to verify wiring
  - Green = face detected, Red = no face, Blue = processing
  - Color-coded expressions (blue=surprise, yellow=eyebrow, green=smile)
  - Controllable from Python via `Bridge.call("set_rgb", "color")`
- **GPIO Placeholders** — pre-configured pins for extending the demo:
  - D7: Relay (Modulino or generic 5V relay)
  - D6: External LED strip (WS2812B NeoPixel-compatible)
  - D5: Piezo buzzer (beep on face detection)
  - D4/D3: General-purpose auxiliary outputs
  - Each has an enable flag — set `enableRelay = true` etc. in sketch.ino
- **Verbose Boot Diagnostics** — comprehensive startup checks on both MCU and MPU:
  - MCU: Serial banner with board specs, pin states, memory, Bridge status
  - MPU: System resources, network interfaces, DNS, CDN reachability, folder tree
  - All output to Serial monitor (MCU) and terminal (MPU/Replit)
- **Bridge Integration** — MCU ↔ MPU communication via `Bridge.provide()` / `Bridge.call()` RPC

## Software Architecture Overview

The software is developed for the Arduino App Lab, leveraging the UNO Q's dual-processor architecture to separate browser-side AI processing from real-time hardware control.

The responsibilities are split as follows:

1. **Browser (WebUI Brick):** Runs MediaPipe Face Landmarker entirely client-side in WASM. The browser handles all face detection, landmark tracking, expression analysis, and HUD rendering — zero cloud dependency for inference.

2. **MPU (Qualcomm QRB2210):** Running Python, this processor hosts the WebUI Brick and coordinates between the browser and MCU. It receives face telemetry via WebSocket, forwards commands to the MCU via Bridge RPC, and runs system diagnostics at boot.

3. **MCU (STM32U585):** Running the Arduino Sketch, this processor handles physical outputs — the 12x8 LED matrix, RGB LED, status LED, and GPIO placeholders. All MCU behavior is event-driven via `Bridge.provide()` callbacks.

4. **Communication (RPC):** The two processors communicate via RPC using the [Arduino_RouterBridge](https://github.com/arduino-libraries/Arduino_RouterBridge) library.

```
┌─────────────────────────────────────────────┐
│  Browser (WebUI Brick)                      │
│  assets/index.html                          │
│  ├─ MediaPipe Face Landmarker (WASM)        │
│  ├─ Canvas overlay (mesh/outline/iris/HUD)  │
│  ├─ RGB LED / GPIO controls (WebSocket)     │
│  └─ WebSocket ↔ python/main.py             │
├─────────────────────────────────────────────┤
│  Linux MPU — Qualcomm QRB2210               │
│  python/main.py                             │
│  ├─ Boot diagnostics (network, CDN, tree)   │
│  ├─ WebUI Brick (serves frontend + WS)      │
│  ├─ Bridge.call() → MCU functions           │
│  ├─ RGB/GPIO forwarding from browser        │
│  └─ Face state tracking & forwarding        │
├─────────────────────────────────────────────┤
│  STM32 MCU — STM32U585                      │
│  sketch/sketch.ino                          │
│  ├─ Verbose Serial boot (specs, pins, mem)  │
│  ├─ RGB LED self-test + status colors       │
│  ├─ Bridge.provide() — 9 RPC handlers       │
│  ├─ 12x8 LED matrix (ArduinoGraphics)       │
│  │   ├─ Scrolling text (IP, RAM, kernel)    │
│  │   ├─ Face bitmaps (smiley, surprise, X)  │
│  │   ├─ Checkmark on successful boot        │
│  │   └─ Flash animation on detection        │
│  ├─ GPIO placeholders (relay, buzzer, aux)  │
│  └─ Status LED (face present indicator)     │
└─────────────────────────────────────────────┘
```

## Project Structure

```
├── app.yaml                 # App Lab manifest — bricks and app metadata
├── python/
│   ├── main.py              # MPU entry — WebUI Brick + Bridge.call()
│   └── requirements.txt     # Python dependencies (none beyond App Lab runtime)
├── sketch/
│   ├── sketch.ino           # MCU entry — Bridge.provide() + LED matrix
│   └── sketch.yaml          # Arduino CLI board profile & library versions
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
| **Boot step 1** | Static text `"UNO"` |
| **Boot step 2** | Scrolls `"BOOTING..."` |
| **Boot step 3** | Checkmark bitmap (✓) |
| **Boot step 4** | Scrolls `"BRIDGE OK"` |
| **Startup 1** | Scrolls `"IP: 192.168.x.x"` |
| **Startup 2** | Scrolls `"RAM: 3800/4096MB"` |
| **Startup 3** | Scrolls kernel version |
| **Waiting** | Scrolls `"Face Demo Ready"` |
| **Face detected (new)** | Rapid flash smiley 3x → hold smiley (+ buzzer beep if enabled) |
| **Face detected (ongoing)** | Smiley bitmap (or expression bitmap) |
| **Expression: smile** | Smiley face bitmap (mouth curve) |
| **Expression: surprise** | O-mouth + wide eyes bitmap |
| **Expression: eyebrow** | Raised eyebrows + neutral mouth |
| **No face** | X pattern |
| **Device switch** | Scrolls `"Mode: uno_q"` or `"Mode: ventuno"` |

## RGB LED Status Colors

The onboard RGB LED provides at-a-glance status without needing a screen:

| Color | Meaning |
|-------|---------|
| Red → Green → Blue | Self-test during boot (300ms each) |
| Red (solid) | Idle / no face detected |
| Green (solid) | Face detected and tracking |
| Blue (solid) | Browser connected / processing |
| Yellow | Eyebrow raise expression |
| Magenta | Unknown/custom expression scroll |
| Off | RGB disabled or between states |

Colors are controllable from Python (`Bridge.call("set_rgb", "green")`) or from the browser via WebSocket (`rgb_control` event).

## GPIO Placeholders

Pre-configured pins for extending the demo with external hardware. All pins are set as OUTPUT at boot but remain LOW unless their enable flag is set to `true` in `sketch.ino`:

| Pin | Name | Default | Use Case |
|-----|------|---------|----------|
| D7 | `PIN_RELAY` | disabled | Modulino Relay or generic 5V relay — energize on face detection |
| D6 | `PIN_EXT_LED` | disabled | WS2812B NeoPixel strip data pin (needs Adafruit_NeoPixel library) |
| D5 | `PIN_BUZZER` | disabled | Piezo buzzer — beep on face detection via `tone()` |
| D4 | `PIN_AUX_1` | disabled | General-purpose — servo, sensor trigger, Modulino accessory |
| D3 | `PIN_AUX_2` | disabled | General-purpose (PWM capable) — LED dimming, motor speed |

To enable a placeholder, edit `sketch.ino`:
```cpp
bool enableRelay  = true;   // was false
bool enableBuzzer = true;   // was false
```

GPIO pins are controllable from Python (and from the browser when running on real hardware via App Lab WebSocket):
- Python: `Bridge.call("set_gpio", "7:1")` (pin 7 HIGH)
- Browser (App Lab only): WebSocket `gpio_control` event with `{pin: 7, state: 1}`

**Safety**: The MCU enforces a pin allowlist — only placeholder pins (D3–D7) can be toggled, and only when their enable flag is `true`. Requests for other pins or disabled pins are blocked and logged to Serial.

## Boot Diagnostics

### MCU Serial Output (sketch.ino)

The MCU prints a detailed diagnostic report to Serial (115200 baud) on every boot:

```
────────────────────────────────────────────────
  WOJO'S UNO Q FACE OUTLINE DEMO
────────────────────────────────────────────────
  Firmware              : Face Demo v1.0
  Board                 : Arduino Uno Q
  MCU                   : STM32U585 (Cortex-M33)
  SoC (MPU side)        : Qualcomm QRB2210
  LED Matrix            : 12x8 built-in
  Compile date          : Apr 07 2026
  ...
────────────────────────────────────────────────
  PIN CONFIGURATION
────────────────────────────────────────────────
  STATUS_LED            : 13 (OUTPUT, LOW)
  RGB LED R/G/B         : 11/12/13
  PIN_RELAY (D7)        : disabled (placeholder)
  ...
────────────────────────────────────────────────
  BOOT COMPLETE
────────────────────────────────────────────────
  Boot time             : 4200ms
  Free memory           : 48320 bytes
  ...
```

### MPU Terminal Output (python/main.py)

The MPU runs a full system diagnostic before the app starts:

```
────────────────────────────────────────────────
  WOJO'S UNO Q FACE OUTLINE DEMO — MPU BOOT
────────────────────────────────────────────────
  Python                : 3.11.14
  Machine               : aarch64
  Kernel                : 5.15.0-qrb2210
  ...
────────────────────────────────────────────────
  NETWORK DIAGNOSTICS
────────────────────────────────────────────────
  Primary IP            : 192.168.1.42
  ✓ DNS resolution OK — google.com → ...
  ...
────────────────────────────────────────────────
  CDN REACHABILITY (browser will need these)
────────────────────────────────────────────────
  ✓ MediaPipe WASM: HTTP 200 OK
  ✓ MediaPipe Model: HTTP 200 OK
  ✓ Google Fonts: HTTP 200 OK
  ...
────────────────────────────────────────────────
  PROJECT FOLDER TREE
────────────────────────────────────────────────
  ├── app.yaml (735B)
  ├── assets/
  │   ├── index.html (61KB)
  ...
```

## Bridge RPC Reference

### MPU → MCU — `Bridge.call()` (Python calls sketch)

| Function | Payload | Purpose |
|----------|---------|---------|
| `scroll_text` | `"IP: 192.168.1.42"` | Scroll any text across the 12x8 matrix |
| `show_face` | — | Display smiley face bitmap + green RGB + relay ON |
| `show_no_face` | — | Display X pattern + red RGB + relay OFF |
| `flash_face` | `3` (count) | Rapidly flash face bitmap N times + buzzer beep |
| `show_expression` | `"smile"`, `"surprise"`, `"eyebrow"` | Show expression bitmap + expression-specific RGB color |
| `set_device_mode` | `"uno_q"` or `"ventuno"` | Switch device mode, scroll confirmation |
| `set_rgb` | `"red"`, `"green"`, `"blue"`, `"yellow"`, `"cyan"`, `"magenta"`, `"white"`, `"off"` | Set RGB LED color |
| `set_gpio` | `"7:1"` (pin:state) | Set any digital pin HIGH/LOW |
| `report_status` | — | Request MCU status report (uptime, faces, memory) |

### MCU → MPU — `Bridge.call()` (sketch calls Python)

| Function | Payload | Purpose |
|----------|---------|---------|
| `mcu_ready` | — | MCU initialization complete |
| `mcu_status_report` | status string | MCU reports uptime, face count, free memory |

### Bridge Registration

**MCU side** (`sketch.ino` → `setup()`): 9 providers registered with `Bridge.provide("name", handler)`. The `loop()` is empty — the sketch is entirely event-driven via Bridge callbacks. A heartbeat example is shown commented out in `loop()` for reference.

**MPU side** (`python/main.py`): Python-side providers use `Bridge.provide("name", handler)`. WebSocket handlers use `ui.on_message("event", handler)` (function-call registration, not decorators).

## WebSocket Events (Browser ↔ MPU)

| Event | Direction | Payload |
|-------|-----------|---------|
| `face_data` | Browser → MPU | `{faces, blinks, expression, pupilL, pupilR, yaw, pitch}` |
| `device_switch` | Browser → MPU | `{"device": "uno_q"}` or `{"device": "ventuno"}` |
| `capture_snapshot` | Browser → MPU | Snapshot request |
| `rgb_control` | Browser → MPU | `{"color": "green"}` — sets MCU RGB LED (App Lab WebSocket only) |
| `gpio_control` | Browser → MPU | `{"pin": 7, "state": 1}` — toggles MCU GPIO (App Lab WebSocket only) |
| `state_update` | MPU → Browser | Full face state JSON |
| `snapshot_ack` | MPU → Browser | `{"status": "ok", "timestamp": "..."}` |

## Dependencies

This project is designed to pull as few external resources as possible.

### MCU (sketch.ino) — Arduino Libraries

| Library | Version | Notes |
|---------|---------|-------|
| `Arduino_RouterBridge` | 0.4.1 | Bridge RPC — primary library in sketch.yaml |
| `ArduinoGraphics` | 1.1.4 | Text/graphics on LED matrix — listed explicitly (App Lab doesn't auto-resolve it) |
| `Arduino_RPClite` | 0.2.1 | Transitive dep of RouterBridge |
| `ArxContainer` | 0.7.0 | Transitive dep of RouterBridge |
| `ArxTypeTraits` | 0.3.2 | Transitive dep of RouterBridge |
| `DebugLog` | 0.8.4 | Transitive dep of RouterBridge |
| `MsgPack` | 0.4.2 | Transitive dep of RouterBridge |
| `Arduino_LED_Matrix` | (platform) | Bundled with arduino:zephyr board core — no separate entry needed |

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
