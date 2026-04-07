# Wojo's Uno Q Face Outline Demo

Real-time face tracking for the Arduino Uno Q (Qualcomm QRB2210), built with the Arduino App Lab and Bricks SDK. Google MediaPipe Face Landmarker runs entirely in the browser -- 478 landmarks, up to 4 faces, zero cloud dependency.

## Architecture

The Uno Q's dual-processor design splits work across three layers. The browser handles all AI inference. The Linux MPU coordinates and serves the frontend. The MCU drives physical outputs.

```
Browser (WebUI Brick)                  assets/index.html
  MediaPipe Face Landmarker (WASM)     478 landmarks per face, 4 faces max
  Canvas overlay                       mesh, outline, iris, HUD, emojis
  Adaptive performance                 auto-skip frames when FPS < 8
  WebSocket telemetry                  face_data, rgb_control, gpio_control
      |
      | WebSocket (JSON, throttled 500ms)
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

Three layers communicate via two protocols: WebSocket (browser to MPU, provided by App Lab WebUI Brick SDK at runtime on real hardware) and Bridge RPC (MPU to MCU). The browser HTML does not contain explicit socket code -- the Brick SDK injects WebSocket messaging at runtime. In the Replit preview, the browser runs standalone without the SDK, so face detection and rendering work but no data reaches the MPU or MCU.

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

The QRB2210's Adreno 650 GPU supports WebGL, but MediaPipe's GPU delegate produces spatially incorrect landmarks despite appearing to work. The app uses CPU-first with automatic runtime validation: 6 sanity checks per frame, 5-frame voting window (majority rules), auto-switch on failure, continuous re-validation every 60 seconds.

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
     |   Bridge: flash_face(3), show_face(), set_rgb("green")
     |
     +- Face -> Face (expression changed)
     |   Bridge: show_expression(expr), set_rgb(expr_color)
     |
     +- Face -> No face
         Bridge: show_no_face(), set_rgb("red")
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
| Board | Arduino Uno Q (QRB2210 + STM32U585) |
| LED Matrix | Built-in 13x8 (no wiring needed) |
| Camera | Standard UVC USB webcam |
| Connection | USB-C hub/dongle |
| Browser | Chrome/Edge on same network |

## Installation

**Option A -- Arduino App Lab Import (recommended):** Download this repository as a `.zip`, open [Arduino App Lab](https://lab.arduino.cc), click Import App, select the `.zip`. App Lab auto-detects `app.yaml` and wires everything up. Deploy to your connected Uno Q. The LED matrix shows the device IP -- open that address in Chrome.

**Option B -- Manual Setup:** Clone this repo to your Uno Q workspace. Ensure the Bricks SDK is installed (`arduino:web_ui`). Flash `sketch/sketch.ino` to the STM32 MCU via App Lab. Run `python/main.py` on the Linux MPU container. Open the displayed IP in your browser.

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

The QRB2210 is a quad-core Cortex-A53 at 2.0 GHz with an Adreno GPU but no Hexagon NPU. TFLite runs on CPU/GPU only. Expected: `face_det_lite` INT8 at ~5-15ms/frame (CPU), with camera capture at 640x480 15 FPS as the practical bottleneck.

**Quick start:**

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

**Helper script** (`python/ai_hub_setup.py`): `--check` (system readiness), `--list` (supported models), `--compile --model face_det_lite` (compile via cloud), `--compile --quantize w8a8` (INT8 quantization), `--download --model face_det_lite` (pre-built), `--verify models/file.tflite` (inspect and test).

**Graceful degradation:** The system always works without AI Hub models. Missing tflite-runtime, numpy, opencv, .tflite model, or /dev/video device all result in browser-only mode (MediaPipe WASM). Boot diagnostics report full AI Hub status.

## Reference Projects

Three reference implementations informed this project's patterns.

**DIY-ECG** (`diy-ecg-uno-Q`): Real-time ECG acquisition. Validates Bridge RPC, WebUI Brick, MsgPack binary frames, CRC-16, ring buffers, and Zephyr k_timer patterns. Data flows hardware-first: sensor -> MCU ADC -> ring buffer -> Bridge RPC <- MPU poll -> WebSocket -> browser.

**Arduino Uno Q Projects** (MartinsRepo): Community collection covering GPIO via Zephyr Devicetree, SPI display drivers (ST7789), Podman containers for MediaPipe/OpenAI, LED matrix flickering fix, and pyenv virtualenv. Documents critical hardware details: pin mapping via gpio_dt_spec at compile time, STM32 boot-time matrix flicker (normal until firmware initializes), and Python version conflicts (MediaPipe needs 3.12, Debian ships 3.13).

**SafeGuard AI** (`dharmsaliya/safeguard-ai`): Fall detection with Modulino Movement (LSM6DSOX) + TFLite INT8. Introduces `Bridge.notify()` (fire-and-forget MCU to MPU, no response), `web_ui.expose_api()` REST endpoints alongside WebSocket, adaptive calibration UI with 15s learning phase, Chart.js sensor plotting, alarm overlay with countdown/cancel/QR, and Twilio emergency calls. TinyML pipeline: 12 features (3 acc + 3 gyro + altitude delta + 2 magnitudes + 3 jerks), 200-sample sliding window at 100Hz, Conv1D INT8 quantized.

**Data flow comparison:**

```
  Face Demo (this project):
    Camera -> Browser WASM -> Canvas overlay
                           +-> WS -> MPU -> Bridge -> MCU (LED/RGB)
    Direction: browser-first, push to hardware

  DIY-ECG:
    Sensor -> MCU ADC -> Ring buffer -> Bridge RPC <- MPU poll
                                                      +-> WS -> Browser
    Direction: hardware-first, pull to browser

  FaceInterpretor:
    Camera -> Podman (MediaPipe + OpenAI) -> HTTP API <- MPU poll
                                                          +-> Bridge -> MCU (SPI)
    Direction: container-first, bridge to display

  SafeGuard AI:
    Sensor -> MCU notify() -> MPU TFLite -> WS -> Browser alarm
                                         -> Twilio API (emergency)
    Direction: hardware-push, AI-on-MPU, dual output
```

## Credits

- [Arduino App Lab](https://docs.arduino.cc/software/app-lab/)
- [Arduino App Bricks](https://github.com/arduino/app-bricks-py)
- [Arduino App Bricks Examples](https://github.com/arduino/app-bricks-examples)
- [Google MediaPipe](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker)
- [Qualcomm AI Hub](https://aihub.qualcomm.com/)
- Qualcomm QRB2210 Dragonwing SoC
- [DIY-ECG Uno Q](https://github.com/diy-ecg/diy-ecg-uno-Q)
- [Arduino Uno Q Projects](https://github.com/MartinsRepo/Arduino-Uno-Q-Projects)
- [SafeGuard AI](https://github.com/dharmsaliya/safeguard-ai)
