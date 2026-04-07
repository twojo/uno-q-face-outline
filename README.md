# Wojo's Uno Q Face Outline Demo

Real-time face tracking for the Arduino Uno Q, built with the Arduino App Lab and Bricks SDK. Google MediaPipe Face Landmarker runs entirely in the browser -- 478 landmarks, up to 4 faces, zero cloud dependency for inference.

## Why the Arduino Uno Q

The [Arduino Uno Q](https://docs.arduino.cc/hardware/uno-q/) is a dual-processor board that combines a Qualcomm Dragonwing QRB2210 application processor running full Debian Linux with a dedicated STM32U585 microcontroller running Arduino sketches on Zephyr OS. This is not a typical Arduino -- it is a single-board computer with an embedded MCU, designed for AI at the edge.

![UNO Q board architecture](https://docs.arduino.cc/static/567189fab6cc1a00404d38e37b42e755/a6d36/uno-q-architecture-3.png)

The QRB2210 MPU provides quad-core Cortex-A53 at 2.0 GHz, an Adreno 702 GPU, dual ISPs for camera input, Wi-Fi 5, Bluetooth 5.1, and 2 GB or 4 GB of LPDDR4 RAM. The STM32U585 MCU provides Cortex-M33 at 160 MHz with 2 MB flash and 786 KB SRAM, running deterministic real-time control. The two processors communicate through a built-in RPC library called Arduino Bridge.

This face tracking demo uses all of it. The browser-side AI model runs on the QRB2210's CPU via WASM. The MCU drives the built-in 13x8 LED matrix and RGB LED to give physical feedback when a face is detected, lost, or changes expression. Bridge RPC ties them together so the Python coordinator on the MPU can forward face state from the browser to the MCU in real time.

![UNO Q pinout](https://docs.arduino.cc/static/c4c115ced208022ab43299bda7ea661e/a6d36/Simple-pinout-ABX00162.png)

For full pinout details, datasheet, schematics, and CAD files, see the [official hardware page](https://docs.arduino.cc/hardware/uno-q/) and the [UNO Q User Manual](https://docs.arduino.cc/tutorials/uno-q/user-manual/).

## The App Lab and Bricks Experience

The [Arduino App Lab](https://docs.arduino.cc/software/app-lab/) is a unified development environment that lets you combine Arduino sketches, Python scripts, and containerized Linux applications into a single workflow. You do not need to manually set up a toolchain, configure a cross-compiler, or wire up a web server -- App Lab and Bricks handle all of that.

[Bricks](https://docs.arduino.cc/software/app-lab/tutorials/bricks) are code building blocks that abstract away complexity. This project uses a single Brick:

- **`arduino:web_ui`** -- serves the contents of `assets/` as a web application and provides WebSocket messaging between the browser and `python/main.py`. The Brick injects WebSocket connectivity at runtime so the browser-side face data can reach the Python coordinator, which then forwards it to the MCU via Bridge RPC. No explicit socket code is needed in the HTML.

Other Bricks are available for object detection, motion detection, speech recognition, and more. Each one deploys as a container on the QRB2210 and exposes an API to your Python application. Adding a Brick to this project would be as simple as editing `app.yaml` and importing it in `python/main.py`.

To install this demo, download the repository as a `.zip`, open [Arduino App Lab](https://www.arduino.cc/en/software/#app-lab-section), click Import App, and select the file. App Lab reads `app.yaml`, compiles the sketch, deploys the Brick, and launches the application. The LED matrix will display the device IP -- open that address in Chrome on any device on the same network.

## Expanding the Hardware

The Uno Q is designed to be expanded. It retains the classic UNO form factor for shield compatibility, and adds two bottom-mounted high-speed connectors (JMEDIA and JMISC) for advanced peripherals.

![UNO form factor](https://docs.arduino.cc/static/7d5a122fd16435d60983ecb96c2e490f/a6d36/uno-form-factor.png)

**Carrier boards** snap onto the bottom connectors and expose interfaces that the UNO headers alone cannot provide:

| Carrier | What it adds |
|---------|-------------|
| [UNO Media Carrier](https://docs.arduino.cc/hardware/uno-media-carrier/) | Dual MIPI-CSI camera connectors (Raspberry Pi compatible), MIPI-DSI display output, three 3.5 mm audio jacks (mic in, line out, ear out) |
| [UNO Breakout Carrier](https://docs.arduino.cc/hardware/uno-breakout-carrier/) | Full breakout of JMEDIA and JMISC signals to 2.54 mm headers -- audio, I2C, SPI, UART, PWM, PSSI, GPIO for oscilloscope probing and custom circuits |

**Qwiic / Modulino sensors** connect via the onboard Qwiic connector (I2C on Wire1) with no soldering. Some modules relevant to this project:

| Modulino | Use with this demo |
|----------|--------------------|
| [Modulino Movement](https://docs.arduino.cc/hardware/modulino-movement/) | LSM6DSOX accelerometer/gyroscope -- detect if the Uno Q is being moved or tilted while tracking |
| [Modulino Distance](https://docs.arduino.cc/hardware/modulino-distance/) | Time-of-flight distance sensor -- measure the viewer's distance from the camera |
| [Modulino Buttons](https://docs.arduino.cc/hardware/modulino-buttons/) | Physical buttons -- cycle overlay presets or toggle tracking without touching the browser |

The GPIO placeholder pins (D3-D7) in this demo are already wired for a relay, buzzer, NeoPixel strip, and two auxiliary outputs. Enabling them is a single flag change in `sketch.ino`.

## Arduino Cloud Integration (Future)

The current demo runs entirely on the local network -- face tracking data stays in the browser and MCU, and everything resets when you reload the page. [Arduino Cloud](https://docs.arduino.cc/arduino-cloud/) could change that.

With an Arduino Cloud integration, the Uno Q could push face detection events to a persistent cloud dashboard. Practical possibilities:

- Log the timestamp and screenshot of each new face detection to a cloud Thing
- Maintain a persistent face count across sessions (total faces detected, daily/weekly)
- Display a live dashboard showing current tracking state, uptime, and system health remotely
- Set up webhook notifications when a face is detected (or when no face has been seen for a threshold period)
- Store historical data with [Arduino Cloud's built-in data export](https://docs.arduino.cc/arduino-cloud/features/iot-cloud-historical-data/) for analysis

The Uno Q's built-in Wi-Fi and the WebUI Brick's `web_ui.expose_api()` pattern (REST endpoints alongside WebSocket) make this feasible without restructuring the app. The MPU-side Python code already has the face state dict and event hooks needed to push data upstream.

## Architecture

```
Browser (WebUI Brick)                  assets/index.html
  MediaPipe Face Landmarker (WASM)     478 landmarks per face, 4 faces max
  Canvas overlay                       mesh, outline, iris, HUD, emojis
  Adaptive performance                 auto-skip frames when FPS < 8
  WebSocket telemetry                  face_data, rgb_control, gpio_control
      |
      | WebSocket (JSON, throttled 500ms)
      | (injected by Brick SDK at runtime on real hardware)
      v
Linux MPU (QRB2210)                    python/main.py
  WebUI Brick                          serves assets/ + WebSocket
  Boot diagnostics                     CPU, RAM, network, DNS, CDN, file tree
  Bridge.call() forwarding             face state -> MCU hardware
  AI Hub fallback                      optional TFLite on-device detection
      |
      | Bridge RPC (Arduino_RouterBridge)
      v
STM32 MCU (STM32U585)                 sketch/sketch.ino
  13x8 LED matrix                      grayscale bitmaps via Arduino_LED_Matrix
  RGB LED (LED4, active-low)           status colors, expression feedback
  Status LED (LED_BUILTIN)             solid = face present
  GPIO placeholders (D3-D7)            relay, buzzer, NeoPixel, aux (all disabled by default)
  9 Bridge providers                   event-driven, loop() is empty
```

## State Diagrams

### 1. Full System Boot Sequence

Both processors boot in parallel. The MCU completes first (no OS) and waits for Bridge; the MPU runs Linux, starts Python, then connects.

```
  MCU (STM32U585)                                MPU (QRB2210 Linux)
  ──────────────                                  ──────────────────
  Power-on                                        Power-on
    |                                               |
    +- Serial.begin(115200)                         +- Linux kernel boot
    +- Print banner + specs                         +- Python runtime start
    +- Configure GPIO pins                          |
    +- matrix.begin()                               +- Import App Lab SDK
    +- Show smiley bitmap (1.2s)                    +- System diagnostics:
    +- Show boot icon (0.8s)                        |   +- CPU/RAM/disk check
    |                                               |   +- Network interfaces
    +- RGB self-test (R->G->B, 300ms each)          |   +- DNS resolution test
    |                                               |   +- CDN reachability
    +- Bridge.begin()                               |   +- Project file tree
    +- Register 9 Bridge providers                  |
    +- Show checkmark bitmap (0.8s)                 +- Bridge.begin()
    +- Bridge.call("mcu_ready") ─────────────────>  +- Receive mcu_ready
    |                                               |   +- _bridge_ready = True
    +- Set RGB red (idle, waiting)                  |
    |                                               |
    |  <────────────────── Bridge.call() ──────     +- safe_bridge_call("scroll_text", IP)
    +- Show smiley (scroll_text handler)            +- safe_bridge_call("scroll_text", RAM)
    |  <────────────────── Bridge.call() ──────     +- safe_bridge_call("scroll_text", kernel)
    +- Show smiley (scroll_text handler)            |
    |                                               +- Start WebUI Brick
    |                                               |   +- Serve assets/index.html
    |  <────────────────── Bridge.call() ──────     +- safe_bridge_call("scroll_text", "Face Demo Ready")
    +- Show smiley (scroll_text handler)            |
    |                                               +- WebSocket server ready
    |                                               +- Log "BOOT COMPLETE"
    |                                               |
    +- Idle -- waiting for Bridge events            +- Idle -- waiting for WS/Bridge

  Note: The scrollText MCU handler currently displays frame_smiley
  rather than scrolling text -- text scrolling requires ArduinoGraphics
  font rendering which is not yet implemented for the Zephyr platform.
```

### 2. Camera Initialization Flow

```
  Page Load
      |
      v
  navigator.mediaDevices.getUserMedia()
      |                    |
   SUCCESS               ERROR
      |                    |
      v                    v
  Got stream          Check error type:
      |                 NotAllowedError -> "Permission denied"
      v                 NotFoundError   -> "No camera found"
  Get track settings    Other           -> Generic error msg
      |                    |
      +- label             v
      +- resolution    Show camera-error overlay with:
      +- frameRate       step-by-step fix instructions,
      +- facingMode      Uno Q setup link,
      +- megapixels      permission guide
      |
      v
  cam.srcObject = stream
      | onloadeddata
      v
  Init FaceLandmarker
      | onReady
      v
  Start draw() render loop
```

### 3. Face Detection and Rendering Pipeline

Every animation frame passes through this pipeline. The adaptive performance system may skip frames to maintain smooth rendering.

```
  requestAnimationFrame(draw)
      |
      v
  cam paused/ended or no model? ── YES ──> return (skip)
      | NO
      v
  Same video frame as last time? ── YES ──> return (skip)
      | NO
      v
  PERF.skipFrames > 0 and not our turn? ── YES ──> increment counters, return
      | NO
      v
  fl.detectForVideo()              <-- MediaPipe WASM inference
  (478 landmarks per face)
      |
      v
  Cap faces to MAX_FACES (4)
      |
      v
  matchFaces()                     <-- Persistent ID assignment
    sorted min-distance                (see Face Tracking Lifecycle)
    adaptive thresholds
    800ms TTL survivors
      |
      v
  For each face:
    +- Draw mesh/outline
    +- Draw iris overlay
    +- Measure pupils (mm)
    +- Calculate blinks (EAR)
    +- Detect expression
    +- Draw emoji icons
    +- Estimate head pose
    +- Draw landmark dots
    +- Draw face label
      |
      v
  drawSysOverlay()                 <-- CPU/RAM/temp stats on canvas
      |
      v
  updateAdaptivePerf()             <-- Check FPS, adjust skip
      |
      v
  Update HUD (every 500ms)        <-- faces, FPS, latency, pupils,
      |                                blinks, yaw/pitch, uptime
      v
  Emit face_data via WebSocket     <-- throttled to 500ms
```

### 4. Adaptive Performance State Machine

Monitors FPS over a sliding window and auto-adjusts frame skipping. Hysteresis gap (8 to 14) prevents rapid toggling.

```
                    +---------------------+
                    |     OPTIMAL          |
                    |  skipFrames = 0      |
                    |  All frames processed|
                    |  Badge: "OPTIMAL"    |
                    +----------+----------+
                               |
                               | avg FPS < 8
                               | (over 3+ samples)
                               v
                    +---------------------+
                    |   AUTO-THROTTLED     |
                    |  skipFrames = 1      |
                    |  Every other frame   |
                    |  Badge: "THROTTLED"  |
                    +----------+----------+
                               |
                               | avg FPS > 14
                               | (sustained recovery)
                               v
                    +---------------------+
                    |     OPTIMAL          |
                    |  FPS history cleared |
                    |  Full speed resumed  |
                    +---------------------+

  Parameters:
    lowFpsThreshold   : 8 FPS
    highFpsThreshold  : 14 FPS
    fpsWindowSize     : 5 samples
    checkInterval     : 2000ms
    Min samples needed: 3
```

### 5. Face Tracking Lifecycle

Each detected face gets a persistent monotonic ID (never recycled) and a unique color from a 4-color palette (blue, orange, green, purple).

```
  New face detected in frame
      |
      v
  matchFaces() distance check
  Compare centroid to all known tracked faces
      |                    |
    MATCHED             UNMATCHED
    (dist < threshold)     |
      |                    |
      v                    v
  Update existing      Assign new ID
    new centroid         nextFaceId++
    reset TTL            Pick color (4 colors)
    update box           Record birth time
      |                    |
      +--------+-----------+
               |
               v
  TRACKED (active)
    Label: "Face N -- 12s"
    Unique color overlay
    Blink/pupil/expression
               |
               | face disappears from detection
               v
  MISSING (TTL countdown)
    800ms grace period
    Face may reappear
      |                |
    REAPPEARS        TTL EXPIRES
    (< 800ms)        (> 800ms)
      |                |
      v                v
  RECOVERED          EXPIRED
    Resume track       Remove from tracked list
    Same ID/color      ID retired
    Reset TTL

  Distance matching: threshold scales with face width, sorted by
  global minimum distance, greedy assignment (closest pair first).
  Max tracked faces: 4 (MAX_FACES).
```

### 6. Bridge Communication Flow (MCU -- MPU -- Browser)

Three layers communicate via two protocols: WebSocket (browser to MPU, provided by the WebUI Brick SDK at runtime on real hardware) and Bridge RPC (MPU to MCU). The browser HTML does not contain explicit socket code -- the Brick SDK injects WebSocket messaging at runtime. In the Replit preview, the browser runs standalone without the SDK, so face detection and rendering work but no data reaches the MPU or MCU.

```
  BROWSER (via WebUI Brick SDK)

    MediaPipe --> face data --> Brick emit("face_data")
    User click --> RGB button --> Brick emit("rgb_control")
    User click --> GPIO toggle --> Brick emit("gpio_control")
    User click --> capture --> Brick emit("capture_snapshot")

    Brick on("state_update") --> update UI
    Brick on("snapshot_ack") --> show confirmation
        |
        | WebSocket (JSON messages)
        v
  MPU (Python)

    on_face_data():
      +- Update face_state dict
      +- Determine expression
      +- safe_bridge_call("show_face") or ("show_no_face")
      +- safe_bridge_call("show_expression", expr)
      +- safe_bridge_call("flash_face", 3) on new face

    on_rgb_control():
      +- safe_bridge_call("set_rgb", color)

    on_gpio_control():
      +- safe_bridge_call("set_gpio", "pin:state")

    safe_bridge_call(method, *args):
      +- try: Bridge.call(method, *args)
      +- except: log error, never crash
    (_bridge_ready flag set by mcu_ready -- informational only)
        |
        | Bridge RPC (Arduino_RouterBridge)
        v
  MCU (STM32U585)

    9 providers registered via Bridge.provide():
      scroll_text(text)    -> display frame_smiley (no text scroll on Zephyr)
      show_face()          -> smiley bitmap + green RGB + relay ON
      show_no_face()       -> X bitmap + red RGB + relay OFF
      flash_face(count)    -> rapid flash N times + buzzer beep
      show_expression(e)   -> expression bitmap + color-coded RGB
      set_device_mode(m)   -> store mode string (no hardware change)
      set_rgb(color)       -> set RGB LED (8 colors + off)
      set_gpio(pin:state)  -> toggle pin if in allowlist and enabled
      report_status()      -> send uptime/faces/mode to MPU

    MCU -> MPU outbound:
      Bridge.call("mcu_ready")          on boot
      Bridge.call("mcu_status_report")  on-demand status string (via report_status)
```

### 7. RGB LED State Machine

LED4 is active-low (LOW = ON, HIGH = OFF). Any color can be set programmatically via `set_rgb`. Supported colors: red, green, blue, yellow, cyan, magenta, white, off.

```
  +----------+     Boot          +------------------+
  |  OFF     | ──────────>       | SELF-TEST        |
  +----------+                   | R -> G -> B      |
                                 | (300ms each)     |
                                 +--------+---------+
                                          |
                                          v
                                 +------------------+
                                 |  RED (idle)       |
                                 |  Waiting for face |
                                 +--------+---------+
                                          |
                           +--------------+--------------+
                           |                             |
                      face detected                 no change
                           |
                           v                             v
                    +-------------+               +-------------+
                    |   GREEN     |               |   RED        |
                    |  (tracking) |               |  (idle)      |
                    +------+------+               +-------------+
                           |
                   expression detected
                           |
              +------------+------------+
              |            |            |
              v            v            v
        +----------+ +----------+ +----------+
        |  GREEN   | |  BLUE    | |  YELLOW  |
        | (smile)  | |(surprise)| | (eyebrow)|
        +----------+ +----------+ +----------+
```

### 8. Overlay Rendering Order

Each frame draws layers in a specific order. The overlay preset controls which layers are visible.

```
  Canvas (cleared each frame)
  ───────────────────────────────────
  Layer 0:  Video frame (via cam element)
  ───────────────────────────────────
  Layer 1:  Face mesh tessellation          toggleable
  Layer 2:  Face contour / jawline          toggleable
  Layer 3:  Eye outline connections         toggleable
  Layer 4:  Eyebrow connections             toggleable
  Layer 5:  Lip connections                 toggleable
  Layer 6:  Face oval (outer contour)       toggleable
  Layer 7:  Iris connections + pupil ring   toggleable
  Layer 8:  Iris diameter measurement       always (when iris visible)
  Layer 9:  Landmark dots (478 per face)    toggleable
  Layer 10: Emoji expression indicators     toggleable
  Layer 11: Blink flash (hot pink)          triggered on blink
  Layer 12: Face label ("Face N -- 12s")    always
  ───────────────────────────────────
  Layer 13: System stats overlay            always (top-right)
  Layer 14: HUD ticker (bottom-center)      always
  ───────────────────────────────────

  Overlay Presets:
  +---------------------+------+---------+------+-------+------+------+----+-------+
  | Preset              | Mesh | Outline | Eyes | Brows | Lips | Iris |Dots| Emoji |
  +---------------------+------+---------+------+-------+------+------+----+-------+
  | Full Mesh+Features  |  Y   |    Y    |  Y   |   Y   |  Y   |  Y   | Y  |   Y   |
  | Outline+Features    |  -   |    Y    |  Y   |   Y   |  Y   |  Y   | -  |   Y   |
  | Mesh Only           |  Y   |    -    |  -   |   -   |  -   |  -   | -  |   -   |
  | Dots Only           |  -   |    -    |  -   |   -   |  -   |  -   | Y  |   -   |
  | Minimal             |  -   |    Y    |  -   |   -   |  -   |  Y   | -  |   -   |
  | Outline+Emojis      |  -   |    Y    |  -   |   -   |  Y   |  -   | -  |   Y   |
  +---------------------+------+---------+------+-------+------+------+----+-------+

  Iris measurement and pupil diameter display are always active
  when the iris layer is enabled in the current preset.
```

### 9. Delegate Selection and Validation Flow

The QRB2210's Adreno 702 GPU supports WebGL, but MediaPipe's GPU delegate produces spatially incorrect landmarks despite appearing to work. The app uses CPU-first with automatic runtime validation: 6 sanity checks per frame, 5-frame voting window (majority rules), auto-switch on failure, continuous re-validation every 60 seconds.

```
  App Start
      |
      v
  Try CPU delegate              <-- preferred (always correct)
  (WASM inference)
      |            |
   SUCCESS       FAIL
      |            |
      v            v
  CPU loaded    Try GPU delegate (WebGL/Adreno)
      |            |            |
      |         SUCCESS       FAIL
      |            |            |
      |            v            v
      |         GPU loaded    FATAL (no delegate)
      |            |
      +------+-----+
             |
             v
  UNTESTED
  Waiting for first face...
             | first face detected
             v
  VALIDATING
  Run 6 sanity checks on each of next 5 frames:
    1. Count = 478
    2. Bounding box > 3%
    3. Out-of-bounds < 20
    4. Nose near center
    5. Eye separation 2-50%
    6. Forehead above chin
             | 5 frames checked
             |
      +------+------+
      |             |
   >= 3 PASS     >= 3 FAIL
      |             |
      v             v
  PASSED         FAILED
      |            auto-switch delegate and reload model
      |
      | continuous check every 60s
      v
  Re-validate 5 frames
  If degraded: warn (no auto-switch)
```

### 10. WebSocket Telemetry Flow

Face data flows from the browser to the MPU, which drives MCU hardware responses.

```
  Browser (every 500ms when faces present)
  ──────────────────────────────────────────
  emit("face_data", {
    faces: 2,
    blinks: {left: 0.1, right: 0.1},
    expression: "smile",
    pupilL: 4.2, pupilR: 4.1,
    yaw: -5.3, pitch: 2.1
  })
      |
      | WebSocket
      v
  MPU (python/main.py :: on_face_data)
  ──────────────────────────────────────────
  1. Parse JSON payload
  2. Update face_state dict
  3. Determine state transition:
     |
     +- No face -> Face appeared
     |   Bridge: flash_face(3), show_face()
     |   (MCU show_face provider sets green RGB internally)
     |
     +- Face -> Face (expression changed)
     |   Bridge: show_expression(expr)
     |   (MCU show_expression provider sets color-coded RGB internally)
     |
     +- Face -> No face
         Bridge: show_no_face()
         (MCU show_no_face provider sets red RGB internally)
  4. Emit state_update to browser
```

## Project Structure

```
app.yaml                  App Lab manifest (bricks: arduino:web_ui)
python/
  main.py                 MPU entry -- WebUI Brick + Bridge forwarding
  face_detector_mpu.py    On-device TFLite face detection wrapper
  ai_hub_setup.py         AI Hub model download/compile helper
  models/                 .tflite model files (auto-discovered at boot)
  requirements.txt        Python dependencies (none beyond App Lab SDK)
sketch/
  sketch.ino              MCU entry -- Bridge.provide() + LED matrix
  sketch.yaml             Arduino CLI board profile and library versions
assets/
  index.html              Full face tracking frontend (self-contained)
  qualcomm-logo.png       Qualcomm branding asset
app.py                    Replit-only Flask server (excluded from App Lab via .gitignore)
templates/index.html      Replit copy of assets/index.html
static/                   Replit static assets
```

## Hardware Requirements

| Component | Details |
|-----------|---------|
| Board | [Arduino Uno Q](https://store.arduino.cc/pages/uno-q) (QRB2210 + STM32U585, 2 GB or 4 GB) |
| LED Matrix | Built-in 13x8 (no wiring needed) |
| Camera | Standard UVC USB webcam |
| Connection | [USB-C multiport adapter](https://store.arduino.cc/products/usb-c-to-hdmi-multiport-adapter-with-ethernet-and-usb-hub) with external power delivery |
| Browser | Chrome or Edge on any device on the same network |

## Installation

Download this repository as a `.zip`. Open [Arduino App Lab](https://www.arduino.cc/en/software/#app-lab-section) (pre-installed on the Uno Q in SBC mode, or install the desktop version on your PC). Click Import App and select the `.zip`. App Lab reads `app.yaml`, compiles the sketch for the STM32 MCU, deploys the WebUI Brick, and launches the application. The LED matrix will display the board's IP address -- open it in Chrome on any device on the same Wi-Fi network.

For manual setup without App Lab: clone this repo to the Uno Q, flash `sketch/sketch.ino` via Arduino IDE 2+, ensure the Bricks SDK is installed, and run `python/main.py` on the Linux side.

## GPIO Placeholders

Pre-configured pins for extending the demo. All set as OUTPUT at boot but remain LOW unless their enable flag is set to `true` in `sketch.ino`. The MCU enforces a pin allowlist -- only D3-D7 can be toggled, and only when their enable flag is `true`. Requests for other pins or disabled pins are blocked and logged.

| Pin | Name | Default | Use Case |
|-----|------|---------|----------|
| D7 | PIN_RELAY | disabled | Modulino Relay or generic 5V relay |
| D6 | PIN_EXT_LED | disabled | WS2812B NeoPixel strip data pin |
| D5 | PIN_BUZZER | disabled | Piezo buzzer (beep on face detection) |
| D4 | PIN_AUX_1 | disabled | General-purpose (servo, sensor, Modulino) |
| D3 | PIN_AUX_2 | disabled | General-purpose (PWM capable) |

To enable: set `enableRelay = true` (etc.) in sketch.ino. Control from Python: `Bridge.call("set_gpio", "7:1")`. Control from browser (App Lab only): WebSocket `gpio_control` event with `{pin: 7, state: 1}`.

## WebSocket Events (Browser -- MPU)

| Event | Direction | Payload |
|-------|-----------|---------|
| `face_data` | Browser -> MPU | `{faces, blinks, expression, pupilL, pupilR, yaw, pitch}` |
| `capture_snapshot` | Browser -> MPU | Snapshot request |
| `rgb_control` | Browser -> MPU | `{"color": "green"}` (App Lab WebSocket only) |
| `gpio_control` | Browser -> MPU | `{"pin": 7, "state": 1}` (App Lab WebSocket only) |
| `state_update` | MPU -> Browser | Full face state JSON |
| `snapshot_ack` | MPU -> Browser | `{"status": "ok", "timestamp": "..."}` |
| `mpu_face_data` | MPU -> Browser | `{faces, source:"mpu", inference_ms, detections}` (AI Hub) |
| `ai_status` | MPU -> Browser | `{available, status, model, running, fps, inference_ms}` |
| `ai_toggle` | Browser -> MPU | `{enable: true/false}` (start/stop on-device detection) |

## Dependencies

Designed to pull as few external resources as possible.

**MCU (sketch.ino):**

| Library | Version | Notes |
|---------|---------|-------|
| Arduino_RouterBridge | 0.4.1 | Bridge RPC (primary dep in sketch.yaml) |
| Arduino_RPClite | 0.2.1 | Transitive dep of RouterBridge |
| ArxContainer | 0.7.0 | Transitive dep of RouterBridge |
| ArxTypeTraits | 0.3.2 | Transitive dep of RouterBridge |
| DebugLog | 0.8.4 | Transitive dep of RouterBridge |
| MsgPack | 0.4.2 | Transitive dep of RouterBridge |
| Arduino_LED_Matrix | (platform) | Bundled with arduino:zephyr board core |

**MPU (python/main.py):** App Lab SDK (`arduino.app_utils`, `arduino.app_bricks.web_ui`) + Python stdlib. Optional for on-device AI: `tflite-runtime`, `numpy`, `opencv-python-headless`. For model compilation on a dev machine (not the Uno Q): `qai-hub`, `qai_hub_models`, `torch`.

**Browser (assets/index.html):**

| Resource | CDN | Pinned | Required |
|----------|-----|--------|----------|
| @mediapipe/tasks-vision | jsdelivr | 0.10.3 | Yes |
| face_landmarker.task model | Google Cloud Storage | float16/1 | Yes (~4MB, cached) |
| Google Fonts (Inter, JetBrains Mono) | Google Fonts | latest | No (degrades to system fonts) |

**Replit preview only (app.py):** `flask` and `psutil`. Both excluded from the App Lab project via `.gitignore`.

## On-Device AI Hub (Optional)

The QRB2210 is a quad-core Cortex-A53 at 2.0 GHz with an Adreno 702 GPU but no Hexagon NPU. TFLite runs on CPU/GPU only. Expected: `face_det_lite` INT8 at ~5-15ms/frame (CPU), with camera capture at 640x480 15 FPS as the practical bottleneck. For NPU-accelerated inference, consider the QCS6490 or QCS8550 (higher-tier Qualcomm boards with Hexagon HTP).

```bash
# On your dev machine -- compile model for QRB2210
pip install qai-hub qai_hub_models torch
qai-hub configure --api_token YOUR_TOKEN
python python/ai_hub_setup.py --compile --model face_det_lite --device QRB2210

# Copy the .tflite file to the Uno Q
scp python/models/face_det_lite.tflite unoq:~/face-demo/python/models/

# On the Uno Q -- install runtime deps
pip install tflite-runtime numpy opencv-python-headless

# Reboot the app -- it auto-discovers the model
```

The system always works without AI Hub models. Missing tflite-runtime, numpy, opencv, .tflite model, or /dev/video device all result in browser-only mode (MediaPipe WASM). Boot diagnostics report full AI Hub status.

## Links

- [Arduino Uno Q Hardware](https://docs.arduino.cc/hardware/uno-q/)
- [UNO Q User Manual](https://docs.arduino.cc/tutorials/uno-q/user-manual/)
- [UNO Q Pinout (PDF)](https://docs.arduino.cc/resources/pinouts/ABX00162-full-pinout.pdf)
- [UNO Q Datasheet (PDF)](https://docs.arduino.cc/resources/datasheets/ABX00162-ABX00173-datasheet.pdf)
- [Arduino App Lab](https://docs.arduino.cc/software/app-lab/)
- [App Lab Bricks](https://docs.arduino.cc/software/app-lab/tutorials/bricks)
- [Arduino Cloud](https://docs.arduino.cc/arduino-cloud/)
- [Google MediaPipe Face Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker)
- [Qualcomm AI Hub](https://aihub.qualcomm.com/)
- [Buy Arduino Uno Q](https://store.arduino.cc/pages/uno-q)
