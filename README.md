# Wojo's Uno Q Face Outline Demo

Real-time face tracking for the Arduino Uno Q, built with the Arduino App Lab and Bricks SDK. Google MediaPipe Face Landmarker runs entirely in the browser -- 478 landmarks, up to 4 faces, zero cloud dependency for inference.

## Why the Arduino Uno Q

The [Arduino Uno Q](https://docs.arduino.cc/hardware/uno-q/) is a dual-processor board that combines a Qualcomm Dragonwing QRB2210 application processor running full Debian Linux with a dedicated STM32U585 microcontroller running Arduino sketches on Zephyr OS. This is not a typical Arduino -- it is a single-board computer with an embedded MCU, designed for AI at the edge.

![UNO Q board architecture](https://docs.arduino.cc/static/567189fab6cc1a00404d38e37b42e755/a6d36/uno-q-architecture-3.png)

The QRB2210 MPU provides quad-core Cortex-A53 at 2.0 GHz, an Adreno 702 GPU, dual ISPs for camera input, Wi-Fi 5, Bluetooth 5.1, and 2 GB or 4 GB of LPDDR4 RAM. The STM32U585 MCU provides Cortex-M33 at 160 MHz with 2 MB flash and 786 KB SRAM, running deterministic real-time control. The two processors communicate through a built-in RPC library called Arduino Bridge.

This face tracking demo uses all of it. The browser-side AI model runs on the QRB2210's CPU via WASM. The MCU drives the built-in 13x8 LED matrix and RGB LED to give physical feedback when a face is detected, lost, or changes expression. Bridge RPC ties them together so the Python coordinator on the MPU can forward face state from the browser to the MCU in real time.

![UNO Q pinout](https://docs.arduino.cc/static/c4c115ced208022ab43299bda7ea661e/a6d36/Simple-pinout-ABX00162.png)

For full pinout details, datasheet, schematics, and CAD files, see the [official hardware page](https://docs.arduino.cc/hardware/uno-q/) and the [UNO Q User Manual](https://docs.arduino.cc/tutorials/uno-q/user-manual/).

## Compute Architecture: What Runs Where

The Uno Q has four distinct compute blocks. Understanding which one handles which part of this demo -- and why -- is the key to understanding how to build on top of it.

![QRB2210 block diagram](https://www.qualcomm.com/content/dam/qcomm-martech/dm-assets/images/pdp/block_diagram/image/QRB2210-diagram.svg)

| Block | Silicon | Clock | Role in this demo |
|-------|---------|-------|-------------------|
| **CPU** | Quad-core Arm Cortex-A53 (Kryo) | 2.0 GHz | Runs Debian Linux, Python coordinator, Docker containers for Bricks, and the Chromium browser that executes MediaPipe WASM face detection |
| **GPU** | Qualcomm Adreno 702 | 845 MHz | OpenGL ES 3.1, Vulkan 1.1, OpenCL 2.0. Available for WebGL rendering and TFLite GPU delegate, but MediaPipe's GPU delegate produces spatially incorrect landmarks on Adreno -- so this demo defaults to CPU |
| **DSP** | Dual-core Qualcomm Hexagon | -- | Handles audio signal processing and always-on low-power tasks. Not directly used by this demo, but available for keyword detection or audio-triggered face capture in future extensions |
| **MCU** | STM32U585 Arm Cortex-M33 | 160 MHz | Runs Arduino sketch on Zephyr OS. Drives the 13x8 LED matrix, RGB LED, status LED, and GPIO pins. Receives commands from the MPU via Bridge RPC. No AI workload -- purely real-time I/O |

The QRB2210 has **no dedicated TPU or NPU** (no TOPS rating). AI inference relies on the CPU and GPU through framework runtimes like TFLite and WASM. This is an intentional tradeoff -- the QRB2210 is Qualcomm's entry-tier IoT processor, optimized for low power and cost rather than raw ML throughput. For NPU-accelerated inference, Qualcomm's higher-tier processors (QCS6490, QCS8550) include the Hexagon Tensor Processor, but those are not available in the UNO form factor today.

**How inference works in this demo:**

```
  Browser (Chromium on QRB2210)
      |
      v
  MediaPipe Face Landmarker
  loaded as WASM module
      |
      v
  CPU delegate (default)          GPU delegate (fallback)
  Cortex-A53 WASM execution       Adreno 702 via WebGL
  ~5-15ms per frame               Available but produces
  Always correct landmarks        spatially incorrect landmarks
      |                           Auto-detected and rejected
      v                           by 6-point validation
  478 landmarks per face          (see State Diagram 9)
  Up to 4 faces simultaneously
      |
      v
  Canvas overlay rendering
  (uses GPU for compositing)
```

The optional on-device TFLite path (AI Hub) runs on the MPU side, bypassing the browser entirely. It captures frames from a USB camera via OpenCV, runs `face_det_lite` INT8 through `tflite-runtime` on the CPU, and sends bounding boxes to the browser via WebSocket. This path is useful when the browser is on a remote device and you want detection to happen on the Uno Q itself.

## Performance Bottlenecks

Where the system slows down and what limits throughput at each stage:

```
  Stage                          Typical Latency       Bottleneck
  ─────────────────────────────────────────────────────────────────
  USB camera capture             ~67ms (15 FPS)        UVC webcam frame rate
  MediaPipe WASM inference       ~5-15ms               CPU (4x A53 cores)
  Canvas rendering (per face)    ~1-2ms                GPU compositing
  WebSocket emit (throttled)     500ms interval        Intentional throttle
  Bridge RPC (MPU -> MCU)        ~2-5ms                Serial transport
  LED matrix update              <1ms                  SPI to matrix driver
  ─────────────────────────────────────────────────────────────────
  Browser-side (camera to overlay)  ~75-90ms           Camera is the ceiling
  Full loop (camera to LED)         ~500-575ms         WebSocket throttle
```

Browser-side rendering (overlay on screen) happens at full frame rate -- the camera frame is the ceiling there. But the MCU hardware response (LED matrix, RGB LED, GPIO) is gated by the 500ms WebSocket telemetry throttle, so the end-to-end latency from camera frame to physical LED change is ~500-575ms. This throttle is intentional to avoid flooding the Bridge RPC channel.

The camera is the dominant bottleneck. The QRB2210's dual ISPs support up to 25 MP at 30 FPS through MIPI-CSI, but this demo uses a standard USB webcam over UVC, which typically delivers 640x480 at 15 FPS. Attaching the [UNO Media Carrier](https://docs.arduino.cc/hardware/uno-media-carrier/) and a MIPI-CSI camera would roughly double the available frame rate and unlock higher resolution input.

The adaptive performance system (State Diagram 4) compensates for CPU contention. When other processes compete for the A53 cores -- Docker containers, system services, additional Bricks -- FPS drops below 8 and the app automatically skips every other frame rather than dropping quality. Recovery to full speed happens when sustained FPS exceeds 14.

Memory is rarely the bottleneck. The 2 GB variant runs this demo comfortably. The 4 GB variant is recommended if you plan to run multiple Bricks simultaneously (object detection + face tracking + web UI) or use the board as a standalone single-board computer with a desktop environment.

## Beyond Face Tracking: Industrial and Pro Applications

This demo is a face tracking proof-of-concept, but the architecture it demonstrates -- browser-side AI inference, Python coordination, real-time MCU control, and Bridge RPC -- applies directly to [Arduino Pro](https://www.arduino.cc/pro/) industrial use cases. The Uno Q's dual-processor design and App Lab workflow are built for exactly this kind of edge AI deployment.

**Access control and visitor management.** Replace the LED matrix feedback with a relay on D7 to control a door strike or turnstile. When a new face appears, the MPU calls `flash_face(3)` on the MCU (rapid LED flash + buzzer alert), then subsequent face-present updates call `show_face()` which sets the relay pin HIGH. When the face disappears, `show_no_face()` drops the relay. Enable the relay by setting `enableRelay = true` in `sketch.ino`. Add Arduino Cloud logging (see below) to maintain a persistent visitor log with timestamps and screenshots.

**Occupancy monitoring.** The persistent face count (`MAX_FACES = 4`) and tracking lifecycle (State Diagram 5) already count concurrent faces and track duration. Forward the face count to a building management system via the MPU's Wi-Fi to control HVAC, lighting, or elevator dispatch based on real-time occupancy.

**Safety compliance.** Swap the MediaPipe face model for an object detection model (the App Lab `arduino:object_detection` Brick uses YOLOX-Nano) to detect PPE, hard hats, safety vests, or missing guards. The MCU can drive a warning buzzer on D5 and a red status light via the RGB LED when non-compliance is detected.

**Quality inspection.** Mount a MIPI-CSI camera via the Media Carrier and point it at a production line. Use the same architecture -- vision model in the browser or via TFLite on the MPU, defect classification in Python, pass/fail signal to MCU GPIO for reject actuators. The Modulino Distance sensor can trigger inspection only when a part is at the correct position.

**Operator presence detection.** In machinery safety, an operator must be present for a machine to run. The face tracking lifecycle's 800ms TTL (State Diagram 5) provides a presence/absence signal with sub-second latency. Wire D7 to a safety interlock relay. Face detected = machine enabled. Face lost for 800ms = machine stop. The MCU handles this at Zephyr real-time priority, independent of Linux process scheduling.

**Retail analytics and smart signage.** Count foot traffic, measure dwell time (tracked face duration), and estimate audience demographics. The multi-face tracking with persistent IDs means you can distinguish between a new visitor and a returning one within a session. Forward aggregated data to Arduino Cloud dashboards for store managers.

**Agriculture and environmental monitoring.** Replace the camera-based AI model with sensor-based Bricks. The Modulino Movement sensor detects equipment vibration. The Modulino Distance sensor monitors fill levels. The MCU drives actuators (pumps, valves, alerts) via GPIO. The same App Lab workflow, Bridge RPC, and Arduino Cloud integration apply -- only the Brick and the model change.

## The App Lab and Bricks Experience

The [Arduino App Lab](https://docs.arduino.cc/software/app-lab/) is a unified development environment that lets you combine Arduino sketches, Python scripts, and containerized Linux applications into a single workflow. You do not need to manually set up a toolchain, configure a cross-compiler, or wire up a web server -- App Lab and Bricks handle all of that.

![Arduino App Lab](https://docs.arduino.cc/static/782ed8393ae066932b79a19418651a50/a6d36/app-lab.png)

[Bricks](https://docs.arduino.cc/software/app-lab/tutorials/bricks) are code building blocks that abstract away complexity. This project uses a single Brick:

- **`arduino:web_ui`** -- serves the contents of `assets/` as a web application and provides WebSocket messaging between the browser and `python/main.py`. The Brick injects WebSocket connectivity at runtime so the browser-side face data can reach the Python coordinator, which then forwards it to the MCU via Bridge RPC. No explicit socket code is needed in the HTML.

Other Bricks are available for object detection, motion detection, speech recognition, and more. Each one deploys as a container on the QRB2210 and exposes an API to your Python application. Adding a Brick to this project is done in the App Lab UI:

![Adding a Brick in App Lab](https://docs.arduino.cc/static/c4ba129c26c39fd5f37d2dfed7fee780/a6d36/add-brick-1.png)

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

The board can be powered via USB-C (5V 3A), the 5V pin, or VIN (7-24V):

![UNO Q power options](https://docs.arduino.cc/static/72456f6873252eb705cfd28538166e8a/a6d36/power-options-3.png)

## Installation

App Lab runs in two modes: directly on the Uno Q as a single-board computer (SBC mode, recommended with the 4 GB variant), or hosted on your PC with the board connected via USB-C.

![SBC and PC hosted modes](https://docs.arduino.cc/static/a149a5e406178f25376d784b1d615e6d/a6d36/modes-2.png)

Download this repository as a `.zip`. Open [Arduino App Lab](https://www.arduino.cc/en/software/#app-lab-section) (pre-installed on the Uno Q in SBC mode, or install the desktop version on your PC). Click Import App and select the `.zip`. App Lab reads `app.yaml`, compiles the sketch for the STM32 MCU, deploys the WebUI Brick, and launches the application. The LED matrix will display the board's IP address -- open it in Chrome on any device on the same Wi-Fi network.

For manual setup without App Lab: clone this repo to the Uno Q, flash `sketch/sketch.ino` via Arduino IDE 2+, ensure the Bricks SDK is installed, and run `python/main.py` on the Linux side.

## First-Time Setup on a Fresh Board

If this is a brand-new Uno Q that has never been connected to App Lab before, expect several update prompts before the demo runs. The order and outcome matter:

**What App Lab will prompt you to update (and what to do):**

| Prompt | What it updates | Recommended action | What happens if you skip |
|--------|----------------|-------------------|-------------------------|
| System firmware | Linux OS image on the QRB2210 MPU | **Accept** — this ensures Wi-Fi, Docker, and the Bricks runtime are current | Demo may work, but you risk kernel/driver incompatibilities with the WebUI Brick |
| Arduino board core (Zephyr) | The Zephyr RTOS platform that runs sketches on the STM32 MCU | **Accept** — `arduino:zephyr` must match the version that `Arduino_RouterBridge 0.4.1` was compiled against | Sketch compilation will likely fail if the core is too old |
| Board firmware (STM32 bootloader) | Low-level MCU bootloader | **Accept** — required for Bridge RPC to function correctly between MCU and MPU | Bridge.begin() may hang or fail silently |
| Brick container updates | Docker images for the WebUI Brick and other App Lab services | **Accept** — the WebUI Brick serves `assets/index.html` and handles WebSocket messaging | The demo cannot start without the WebUI Brick container |

**After accepting all updates:**

1. The board will reboot (possibly more than once). Wait for the green power LED to stabilize — this can take 60-90 seconds on first boot after a firmware update.
2. Connect the board to Wi-Fi if not already configured (App Lab > Settings > Network). The demo requires internet access to download MediaPipe (~4 MB) from cdn.jsdelivr.net on first load. After the first successful load, the browser caches the WASM engine and model.
3. Import the demo `.zip` and let App Lab compile the sketch. Compilation takes ~30-60 seconds. The LED matrix will show a boot icon, then a checkmark, then scroll the board's IP address.
4. Open the displayed IP address in Chrome on any device on the same Wi-Fi network. If you see a blank screen instead of the camera view, check the diagnostics panel (scroll down) — it will tell you which step failed (usually network or camera).

**If something doesn't work after import:**

- **Blank screen, no error**: The JavaScript module failed to load. Open the browser developer console (F12) and look for network errors. Usually means cdn.jsdelivr.net is unreachable — check Wi-Fi.
- **"Cannot Load Face Detection Engine" overlay**: The board has no internet. Connect to Wi-Fi and hit the Retry button on the overlay.
- **LED matrix stays on boot icon (never shows checkmark)**: Bridge.begin() is stuck. This usually means a core/firmware version mismatch. Go back to App Lab and accept all pending updates, then re-import.
- **"No Camera Detected" overlay**: Plug a USB webcam into any USB-A port on the Uno Q. The built-in MIPI-CSI connector requires the Arduino Media Carrier board.
- **Camera permission denied**: The browser on the Uno Q may block camera access by default. Check browser settings > Site permissions > Camera > Allow.
- **MCU shows red LED but Python logs say "MCU ready"**: Normal — the MCU starts in red (idle/waiting). It turns green when the first face is detected.
- **Sketch won't compile**: Make sure `arduino:zephyr` board core is installed and up to date. The sketch depends on `Arduino_RouterBridge 0.4.1` which requires specific Zephyr core versions.

**Recovery if you declined updates:**

If you said "No" to one or more update prompts and the demo doesn't work, you can trigger updates manually:
1. Open App Lab settings
2. Check for board/firmware/core updates
3. Accept all pending updates
4. Reboot the board
5. Re-import the demo `.zip`

The MCU sketch includes an acknowledgement-driven retry mechanism — it re-sends the `mcu_ready` signal to the Python side every 3 seconds for up to 3 minutes after boot. Once the MPU receives the signal, it sends `mpu_ack` back to the MCU, which immediately stops retrying. This means even if the MPU takes a long time to start (common after firmware updates that trigger a full OS reboot), the Bridge connection will be established automatically as soon as both sides are ready.

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

## Where AI Models Come From: AI Hub, Bricks, Hugging Face, and Custom Models

This demo uses Google MediaPipe in the browser, but the Uno Q can run models from many different sources. Understanding which source to use -- and why -- depends on where you want inference to happen, how much optimization you need, and whether you want to bring your own model.

### What is Qualcomm AI Hub?

[Qualcomm AI Hub](https://aihub.qualcomm.com/) is a cloud service that takes pre-trained AI models (PyTorch, ONNX, TensorFlow) and compiles them into optimized runtimes for specific Qualcomm chipsets. You upload a model, select a target device (like the QRB2210), and AI Hub returns a `.tflite`, `.dlc`, or `.bin` file that has been profiled for that exact silicon. Quantization (INT8, INT16) is available as an option during compilation -- it is not automatic, but AI Hub makes it straightforward by handling calibration and conversion in the cloud.

A standard TFLite model already benefits from TFLite's built-in optimized kernels and XNNPACK delegate. AI Hub goes further by applying device-specific operator fusion, memory layout tuning, and optional quantization that can improve inference time significantly -- the exact speedup depends on the model architecture, input size, and workload. For boards with a Hexagon NPU (QCS6490, QCS8550), AI Hub can also compile models that run on the DSP/NPU rather than the CPU, which typically brings much larger speedups.

The QRB2210 in the Uno Q has **no NPU** -- only CPU and Adreno 702 GPU. That means AI Hub's main value for this board is operator fusion and optional quantization, not NPU offloading. You can still see meaningful improvements (the included `ai_hub_setup.py` helper supports `--quantize` for INT8 quantization), but you are not getting the dramatic NPU-accelerated inference that higher-tier Qualcomm boards offer.

### Why this demo uses browser-side MediaPipe instead of AI Hub

This demo defaults to Google MediaPipe running in the browser via WASM for several reasons:

1. **Zero setup.** MediaPipe loads from a CDN -- no model compilation, no Python dependencies, no camera driver configuration. Import the zip, open the browser, and it works.
2. **478 landmarks.** MediaPipe Face Landmarker provides full 3D face geometry (478 points), expression blendshapes, and iris tracking. The AI Hub `face_det_lite` model only provides bounding boxes -- no landmarks, no expressions, no pupil data.
3. **Browser handles the camera.** The browser's `getUserMedia` API manages camera permissions, resolution negotiation, and frame delivery. Running inference on the MPU side requires OpenCV, v4l2 camera access, and manual frame capture -- additional complexity that can fail on first boot.
4. **Works without the Uno Q.** Because inference runs client-side, you can open the demo on any laptop or phone browser to evaluate it before deploying to hardware. The Replit preview uses this mode.

The trade-off is that browser-side inference ties the detection loop to the browser process. If the browser tab is closed, detection stops. The on-device AI Hub path (below) runs headless on the MPU, independent of any browser connection.

### On-device inference via AI Hub (optional)

The `python/face_detector_mpu.py` module and `python/ai_hub_setup.py` helper implement an alternative path: face detection runs natively on the QRB2210 MPU using `tflite-runtime`, bypassing the browser entirely.

```
Camera (v4l2/USB) → OpenCV capture → TFLite inference (CPU) → face results
                                                               ├→ Bridge → MCU (LED/RGB)
                                                               └→ WebSocket → Browser (overlay)
```

This path is useful when:
- You want detection to run headless (no browser open)
- The browser is on a remote device and you want to minimize latency
- You are building a production system that cannot depend on a browser tab

**Hardware constraints on the QRB2210:**

| Spec | Value | Impact |
|------|-------|--------|
| CPU | Cortex-A53 @ 2.0 GHz (4 cores) | TFLite runs here. INT8 face_det_lite: ~5-15ms/frame |
| GPU | Adreno 702 @ 845 MHz | TFLite GPU delegate available but slower than CPU for small models. MediaPipe GPU delegate produces incorrect landmarks |
| NPU/TPU | None (0 TOPS) | No hardware neural network accelerator. This is an entry-tier IoT SoC |
| Camera | USB (UVC) or MIPI-CSI via Media Carrier | 640x480 @ 15 FPS is the practical ceiling for USB webcams. MIPI-CSI supports higher resolution |
| RAM | 2 GB or 4 GB LPDDR4 | Model + OpenCV + TFLite runtime uses ~80-120 MB |

**Setup:**

```bash
# On your dev machine -- compile model for QRB2210 via AI Hub cloud
pip install qai-hub qai_hub_models torch
qai-hub configure --api_token YOUR_TOKEN
python python/ai_hub_setup.py --compile --model face_det_lite --device QRB2210

# Copy the .tflite file to the Uno Q
scp python/models/face_det_lite.tflite unoq:~/face-demo/python/models/

# On the Uno Q -- install runtime deps
pip install tflite-runtime numpy opencv-python-headless

# Reboot the app -- it auto-discovers .tflite files in python/models/ at boot
```

The system always works without AI Hub models. Missing `tflite-runtime`, `numpy`, `opencv`, `.tflite` model, or `/dev/video` device all result in graceful fallback to browser-only mode (MediaPipe WASM). Boot diagnostics report full AI Hub status under the "AI HUB -- ON-DEVICE FACE DETECTION" section.

### Using an App Lab Brick instead

App Lab Bricks are containerized AI services that run as Docker containers on the QRB2210. Arduino provides several pre-built Bricks for common tasks:

| Brick | What it does | Model |
|-------|-------------|-------|
| `arduino:object_detection` | Detects objects in camera frames | YOLOX-Nano |
| `arduino:motion_detection` | Detects motion in video stream | Frame differencing |
| `arduino:web_ui` | Serves web content + WebSocket messaging | (no AI model) |

To add a Brick, edit `app.yaml`:

```yaml
bricks:
  - arduino:web_ui
  - arduino:object_detection
```

Or add it through the App Lab UI. Each Brick deploys as a container on the QRB2210 and exposes an API to your Python code.

**When to use a Brick vs AI Hub vs browser-side:**

| Approach | Where it runs | Setup effort | Model flexibility | Best for |
|----------|--------------|-------------|-------------------|----------|
| Browser (MediaPipe WASM) | Client browser, CPU | Zero -- loads from CDN | Fixed to MediaPipe models | Demos, rapid prototyping, face landmarks |
| App Lab Brick | QRB2210 Docker container | Low -- add one line to app.yaml | Fixed to Arduino's pre-built models | Standard tasks (object detection, motion) |
| AI Hub TFLite | QRB2210 MPU native | Medium -- compile + install deps | Any model from AI Hub's catalog (~100+ models) | Optimized headless inference, Qualcomm-tuned models |
| Hugging Face model | QRB2210 MPU native | Medium-High -- export to TFLite + install deps | TFLite-exportable models from Hugging Face Hub | Custom/niche tasks, research models (must convert to TFLite) |
| Custom model (Edge Impulse, etc.) | QRB2210 MPU native | High -- train + export + deploy | Your own trained model | Domain-specific tasks, proprietary data |

### Bringing a Hugging Face model

Models on [Hugging Face Hub](https://huggingface.co/) that can be exported to TFLite format can run on the Uno Q's MPU using the same `tflite-runtime` infrastructure. Note: this project only includes a TFLite runtime -- ONNX models would require adding `onnxruntime` separately, which is not set up in this demo.

The TFLite export workflow:

1. **Export to TFLite.** Some Hugging Face vision models support export via Hugging Face `optimum`:
   ```bash
   pip install optimum[exporters]
   optimum-cli export tflite --model google/vit-base-patch16-224 --quantize int8 vit_int8.tflite
   ```
   Not all architectures are supported by `optimum`'s TFLite exporter -- check [Hugging Face's supported architectures](https://huggingface.co/docs/optimum/exporters/tflite/overview) before assuming a model will export cleanly. Alternatively, use AI Hub to compile a Hugging Face model for the QRB2210 specifically -- AI Hub supports many popular architectures (MobileNet, EfficientNet, YOLO variants, ViT, DeepLab, Whisper, etc.) and handles the conversion and optimization in the cloud.

2. **Drop the `.tflite` into `python/models/`.** The `face_detector_mpu.py` module auto-discovers `.tflite` files at boot. For models with different input/output signatures, you would need to modify `face_detector_mpu.py` to match (input shape, preprocessing, output parsing).

3. **Run inference.** The same `tflite-runtime` that runs AI Hub models runs any valid TFLite model. No additional runtime is needed for TFLite files.

The main consideration is model size and architecture. The QRB2210 has no NPU, so all inference runs on the CPU (or GPU delegate, though results vary). Large models (>50M parameters) will be impractically slow. Stick to mobile-optimized architectures designed for edge deployment: MobileNetV2/V3, EfficientNet-Lite, NanoDet, PicoDet, or quantized YOLO variants. Actual FPS depends heavily on the model's input resolution, operator mix, and pre/post-processing pipeline, so always benchmark on-device before committing to a model. As a rough guide, models under 5M parameters with 320x320 or smaller input tend to run comfortably on the A53 cores.

### Bringing a custom Edge Impulse model

[Edge Impulse](https://edgeimpulse.com/) is a platform for training custom ML models on your own data and deploying them to edge devices. This is the approach when you need to detect something specific that no pre-trained model covers -- your company's product defects, a specific gesture, a particular plant disease, etc.

Edge Impulse supports TFLite export, which means models trained there can run on the Uno Q the same way AI Hub models do:

1. **Train in Edge Impulse.** Collect data, label it, train a model using Edge Impulse Studio. Choose an architecture appropriate for the A53 (MobileNetV2 or a custom DSP block).

2. **Export as TFLite.** Edge Impulse > Deployment > TensorFlow Lite (int8 quantized). Download the `.tflite` file.

3. **Deploy to the Uno Q.** Copy the `.tflite` file to `python/models/`. Modify `face_detector_mpu.py` to match the model's input shape and output format (Edge Impulse models may output class probabilities rather than bounding boxes).

4. **MCU integration stays the same.** The Python coordinator calls the same Bridge providers (`show_face`, `show_no_face`, `set_rgb`, `set_gpio`) regardless of which model produced the detection. The MCU does not care where the inference happened -- it only responds to Bridge commands.

Edge Impulse also has a direct Arduino library export path (Arduino Library > Deployment), but that targets the STM32 MCU, not the QRB2210 MPU. For the Uno Q, the MCU is too constrained for most ML models (Cortex-M33, 786 KB SRAM). Use the TFLite export to the MPU side instead.

### The decision tree

```
Do you need face landmarks (478 points, expressions, iris)?
  YES → Browser-side MediaPipe (this demo's default)
  NO  → Continue below

Is there a pre-built App Lab Brick for your task?
  YES → Use the Brick (one line in app.yaml, zero code)
  NO  → Continue below

Is the model available on Qualcomm AI Hub?
  YES → Use AI Hub to compile an optimized TFLite for QRB2210
  NO  → Continue below

Is the model available on Hugging Face?
  YES → Export to TFLite (optimum or manual), deploy to python/models/
  NO  → Continue below

Do you have your own training data?
  YES → Train in Edge Impulse, export TFLite, deploy to python/models/
  NO  → Check if a generic model exists elsewhere (TF Model Garden,
        ONNX Model Zoo, etc.) and convert to TFLite
```

In all cases, the MCU layer (`sketch.ino`), the Bridge providers, the WebSocket events, and the Python coordinator structure remain the same. Only the inference source changes. This is the architectural advantage of the Uno Q's dual-processor design -- the AI model is decoupled from the real-time control layer.

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
- [Qualcomm AI Hub Models](https://aihub.qualcomm.com/models)
- [Hugging Face Hub](https://huggingface.co/models)
- [Edge Impulse](https://edgeimpulse.com/)
- [TensorFlow Lite Model Garden](https://www.tensorflow.org/lite/models)
- [Buy Arduino Uno Q](https://store.arduino.cc/pages/uno-q)
