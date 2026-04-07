# Wojo's Uno Q Face Outline Demo

Real-time face tracking demo for the **Arduino Uno Q** (Qualcomm QRB2210) built with the **Arduino App Lab** and **Bricks SDK**.

Uses Google MediaPipe Face Landmarker (478 landmarks, up to 4 faces) running entirely in the browser — zero cloud dependency for inference.

## Features

- **Face Mesh & Outline** — real-time 478-point landmark overlay with configurable mesh, contour, iris, and oval rendering
- **Expression Emojis** — detects smile, surprise, eyebrow raise, and maps to emoji overlay
- **Blink Detection** — real-time blink counter with EAR (Eye Aspect Ratio) algorithm
- **Pupil Diameter** — iris circle overlay with estimated diameter in mm (always enabled)
- **Head Pose** — yaw/pitch estimation from landmark geometry
- **Adaptive Performance** — auto-skips frames when FPS drops below threshold, recovers when performance improves; perf badge shows OPTIMAL/AUTO-THROTTLED
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

## State Diagrams & Flow Charts

This section provides visual documentation of every major subsystem — the states they pass through, what triggers transitions, and how the pieces connect end-to-end.

### 1. Full System Boot Sequence

Both processors boot in parallel. The MCU completes first (no OS) and waits for Bridge; the MPU runs Linux, starts the Python runtime, then connects.

```
  MCU (STM32U585)                                MPU (QRB2210 Linux)
  ──────────────                                  ──────────────────
  Power-on                                        Power-on
    │                                               │
    ├─ Serial.begin(115200)                         ├─ Linux kernel boot
    ├─ Print banner + specs                         ├─ Python runtime start
    ├─ Configure GPIO pins                          │
    ├─ matrix.begin()                               ├─ Import App Lab SDK
    ├─ Show smiley bitmap (1.2s)                    ├─ System diagnostics:
    ├─ Show boot icon (0.8s)                        │   ├─ CPU/RAM/disk check
    │                                               │   ├─ Network interfaces
    ├─ RGB self-test (R→G→B, 300ms each)            │   ├─ DNS resolution test
    │                                               │   ├─ CDN reachability
    ├─ Bridge.begin()                               │   └─ Project file tree
    ├─ Register 9 Bridge providers                  │
    ├─ Show checkmark bitmap (0.8s)                 ├─ Bridge.begin()
    ├─ Bridge.call("mcu_ready") ──────────────────> ├─ Receive mcu_ready
    │                                               │   └─ _bridge_ready = True
    ├─ Set RGB red (idle, waiting)                  │
    │                                               │
    │  <────────────────────── Bridge.call() ─────  ├─ safe_bridge_call("scroll_text", IP)
    ├─ Show smiley (scroll_text handler)            ├─ safe_bridge_call("scroll_text", RAM)
    │  <────────────────────── Bridge.call() ─────  ├─ safe_bridge_call("scroll_text", kernel)
    ├─ Show smiley (scroll_text handler)            │
    │                                               ├─ Start WebUI Brick
    │                                               │   └─ Serve assets/index.html
    │  <────────────────────── Bridge.call() ─────  ├─ safe_bridge_call("scroll_text", "Face Demo Ready")
    ├─ Show smiley (scroll_text handler)            │
    │                                               ├─ WebSocket server ready
    │                                               ├─ Log "BOOT COMPLETE"
    │                                               │
    └─ Idle — waiting for Bridge events             └─ Idle — waiting for WS/Bridge

  Note: The scrollText MCU handler currently displays frame_smiley
  rather than scrolling text — text scrolling requires ArduinoGraphics
  font rendering which is not yet implemented for the Zephyr platform.
```

### 2. Camera Initialization Flow

The browser requests camera access through a multi-step process with error handling at each stage.

```
  ┌────────────┐
  │  Page Load │
  └─────┬──────┘
        │
        v
  ┌─────────────────────┐
  │ navigator.mediaDevices│
  │   .getUserMedia()    │
  └─────┬───────────┬────┘
        │           │
     SUCCESS      ERROR
        │           │
        v           v
  ┌──────────┐  ┌──────────────────────────┐
  │ Got      │  │ Check error type:         │
  │ Stream   │  │  NotAllowedError         │
  └────┬─────┘  │   → "Permission denied"  │
       │        │  NotFoundError            │
       v        │   → "No camera found"    │
  ┌──────────┐  │  Other                   │
  │ Get track│  │   → Generic error msg    │
  │ settings │  └───────────┬──────────────┘
  └────┬─────┘              │
       │                    v
       ├─ label         ┌────────────────────────┐
       ├─ resolution    │ Show camera-error       │
       ├─ frameRate     │ overlay with:           │
       ├─ facingMode    │  • Step-by-step fix     │
       ├─ megapixels    │  • Uno Q setup link     │
       │                │  • Permission guide     │
       v                └────────────────────────┘
  ┌──────────────┐
  │ cam.srcObject│
  │ = stream     │
  └──────┬───────┘
         │ onloadeddata
         v
  ┌──────────────┐
  │ Init         │
  │ FaceLandmarker│
  └──────┬───────┘
         │ onReady
         v
  ┌──────────────┐
  │ Start draw() │
  │ render loop  │
  └──────────────┘
```

### 3. Face Detection & Rendering Pipeline

Every animation frame passes through this pipeline. The adaptive performance system may skip frames to maintain smooth rendering.

```
  requestAnimationFrame(draw)
        │
        v
  ┌─────────────────┐     YES
  │ cam paused/ended ├──────────> return (skip)
  │ or no model?     │
  └────────┬────────┘
           │ NO
           v
  ┌─────────────────┐     YES
  │ Same video frame ├──────────> return (skip)
  │ as last time?    │
  └────────┬────────┘
           │ NO
           v
  ┌──────────────────────┐   YES
  │ PERF.skipFrames > 0  ├────────> increment counters, return
  │ && not our turn?     │
  └────────┬─────────────┘
           │ NO
           v
  ┌──────────────────────┐
  │ fl.detectForVideo()  │ ◄── MediaPipe WASM inference
  │ (478 landmarks/face) │
  └────────┬─────────────┘
           │
           v
  ┌──────────────────────┐
  │ Cap faces to          │
  │ MAX_FACES (4)         │
  └────────┬─────────────┘
           │
           v
  ┌──────────────────────┐
  │ matchFaces()          │ ◄── Persistent ID assignment
  │ • sorted min-distance │     (see Face Tracking Lifecycle)
  │ • adaptive thresholds │
  │ • 800ms TTL survivors │
  └────────┬─────────────┘
           │
           v
  ┌──────────────────────┐
  │ For each face:        │
  │  ├─ Draw mesh/outline │
  │  ├─ Draw iris overlay │
  │  ├─ Measure pupils    │
  │  ├─ Calculate blinks  │
  │  ├─ Detect expression │
  │  ├─ Draw emoji icons  │
  │  ├─ Estimate head pose│
  │  ├─ Draw landmark dots│
  │  └─ Draw face label   │
  └────────┬─────────────┘
           │
           v
  ┌──────────────────────┐
  │ drawSysOverlay()      │ ◄── CPU/RAM/temp stats on canvas
  └────────┬─────────────┘
           │
           v
  ┌──────────────────────┐
  │ updateAdaptivePerf()  │ ◄── Check FPS, adjust skip
  └────────┬─────────────┘
           │
           v
  ┌──────────────────────┐
  │ Update HUD (every     │ ◄── faces, FPS, latency, pupils,
  │ 500ms)                │     blinks, yaw/pitch, uptime
  └────────┬─────────────┘
           │
           v
  ┌──────────────────────┐
  │ Emit face_data via    │ ◄── WebSocket to MPU (every 500ms)
  │ WebSocket (throttled) │
  └──────────────────────┘
```

### 4. Adaptive Performance State Machine

The system monitors FPS over a sliding window and auto-adjusts frame skipping to prevent the UI from becoming unresponsive on slower hardware.

```
                      ┌─────────────────────┐
                      │     OPTIMAL          │
                      │  skipFrames = 0      │
                      │  All frames processed│
                      │  Badge: "OPTIMAL"    │
                      └──────────┬───────────┘
                                 │
                                 │ avg FPS < 8
                                 │ (over 3+ samples)
                                 │
                                 v
                      ┌─────────────────────┐
                      │   AUTO-THROTTLED     │
                      │  skipFrames = 1      │
                      │  Every other frame   │
                      │  Badge: "THROTTLED"  │
                      └──────────┬───────────┘
                                 │
                                 │ avg FPS > 14
                                 │ (sustained recovery)
                                 │
                                 v
                      ┌─────────────────────┐
                      │     OPTIMAL          │
                      │  FPS history cleared │
                      │  Full speed resumed  │
                      └─────────────────────┘

  Parameters:
  ┌────────────────────────────────────┐
  │ lowFpsThreshold   : 8 FPS         │
  │ highFpsThreshold  : 14 FPS        │
  │ fpsWindowSize     : 5 samples     │
  │ checkInterval     : 2000ms        │
  │ Min samples needed: 3             │
  └────────────────────────────────────┘

  Hysteresis gap (8→14) prevents rapid toggling between states.
```

### 5. Face Tracking Lifecycle

Each detected face is assigned a persistent ID and tracked across frames using sorted global-minimum distance matching.

```
  New face detected in frame
        │
        v
  ┌──────────────────────────────┐
  │ matchFaces() distance check   │
  │ Compare centroid to all       │
  │ known tracked faces           │
  └──────┬────────────┬──────────┘
         │            │
    MATCHED         UNMATCHED
    (dist < threshold)   │
         │            │
         v            v
  ┌──────────────┐  ┌──────────────────┐
  │ Update        │  │ Assign new ID     │
  │ existing face │  │ nextFaceId++      │
  │ • new centroid│  │ Pick color from   │
  │ • reset TTL  │  │ palette (4 colors)│
  │ • update box │  │ Record birth time │
  └──────┬───────┘  └────────┬─────────┘
         │                   │
         └─────────┬─────────┘
                   │
                   v
  ┌───────────────────────────┐
  │ TRACKED (active)           │
  │ • Label: "Face N · 12s"   │
  │ • Unique color overlay    │
  │ • Blink/pupil/expression  │
  └──────────┬────────────────┘
             │
             │ face disappears
             │ from detection
             v
  ┌───────────────────────────┐
  │ MISSING (TTL countdown)    │
  │ • 800ms grace period      │
  │ • Face may reappear       │
  └──────┬────────────┬───────┘
         │            │
     REAPPEARS    TTL EXPIRES
     (< 800ms)    (> 800ms)
         │            │
         v            v
  ┌──────────────┐  ┌──────────────┐
  │ RECOVERED     │  │ EXPIRED       │
  │ Resume track  │  │ Remove from   │
  │ Same ID/color │  │ tracked list  │
  │ Reset TTL     │  │ ID retired    │
  └──────────────┘  └──────────────┘

  Distance Matching Details:
  ┌─────────────────────────────────────────────┐
  │ • Threshold scales with face width          │
  │ • Sorted by global minimum distance         │
  │ • Greedy assignment (closest pair first)     │
  │ • Max tracked faces: 4 (MAX_FACES)          │
  │ • Colors: blue, orange, green, purple       │
  └─────────────────────────────────────────────┘
```

### 6. Bridge Communication Flow (MCU ↔ MPU ↔ Browser)

Three layers communicate via two different protocols: WebSocket (browser↔MPU) and Bridge RPC (MPU↔MCU). The WebSocket layer is provided by the App Lab WebUI Brick runtime — the browser-side emit/on calls are handled by the Bricks SDK, not custom JavaScript in `assets/index.html`.

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                  BROWSER (via WebUI Brick SDK)                  │
  │                                                                 │
  │  MediaPipe ──> face data ──> Brick emit("face_data")            │
  │  User click ──> RGB button ──> Brick emit("rgb_control")        │
  │  User click ──> GPIO toggle ──> Brick emit("gpio_control")      │
  │  User click ──> capture ──> Brick emit("capture_snapshot")      │
  │                                                                 │
  │  Brick on("state_update") ──> update UI                         │
  │  Brick on("snapshot_ack") ──> show confirmation                 │
  │                                                                 │
  │  (These calls use the App Lab WebUI Brick runtime. In the       │
  │   Replit preview, the browser runs standalone without the       │
  │   Brick SDK — face detection and rendering are fully local.)    │
  └──────────────────────────┬──────────────────────────────────────┘
                             │ WebSocket
                             │ (JSON messages)
                             v
  ┌─────────────────────────────────────────────────────────────────┐
  │                     MPU (Python)                                │
  │                                                                 │
  │  on_face_data():                                                │
  │    ├─ Update face_state dict                                    │
  │    ├─ Determine expression                                     │
  │    ├─ safe_bridge_call("show_face") or ("show_no_face")         │
  │    ├─ safe_bridge_call("show_expression", expr)                 │
  │    └─ safe_bridge_call("flash_face", 3) on new face            │
  │                                                                 │
  │  on_rgb_control():                                              │
  │    └─ safe_bridge_call("set_rgb", color)                        │
  │                                                                 │
  │  on_gpio_control():                                             │
  │    └─ safe_bridge_call("set_gpio", "pin:state")                 │
  │                                                                 │
  │  safe_bridge_call(method, *args):                               │
  │    ├─ try: Bridge.call(method, *args)                           │
  │    └─ except: log error, never crash                            │
  │  (_bridge_ready flag set by mcu_ready — informational only)     │
  └──────────────────────────┬──────────────────────────────────────┘
                             │ Bridge RPC
                             │ (MsgPack over serial)
                             v
  ┌─────────────────────────────────────────────────────────────────┐
  │                     MCU (Arduino)                               │
  │                                                                 │
  │  9 Bridge.provide() handlers:                                   │
  │    scroll_text(msg)    ──> matrix.textScrollSpeed(100)          │
  │    show_face()         ──> smiley bitmap + RGB green + relay ON │
  │    show_no_face()      ──> X bitmap + RGB red + relay OFF       │
  │    flash_face(count)   ──> rapid bitmap flash + buzzer          │
  │    show_expression(e)  ──> expression bitmap + RGB color        │
  │    set_device_mode(m)  ──> store mode string (no HW change)     │
  │    set_rgb(color)      ──> parse color → set R/G/B pins         │
  │    set_gpio(pin:state) ──> validate allowlist → digitalWrite    │
  │    report_status()     ──> Bridge.call("mcu_status_report")     │
  └─────────────────────────────────────────────────────────────────┘
```

### 7. RGB LED State Machine

The onboard RGB LED provides visual status without requiring a screen. LED4 is active-low (LOW=ON, HIGH=OFF).

```
  ┌────────────────┐
  │   POWER ON      │
  └───────┬────────┘
          │
          v
  ┌────────────────┐  300ms   ┌────────────────┐  300ms   ┌────────────────┐
  │   RED           ├────────>│   GREEN         ├────────>│   BLUE          │
  │   (self-test)   │         │   (self-test)   │         │   (self-test)   │
  └────────────────┘          └────────────────┘          └───────┬────────┘
                                                                  │
                                                                  v
                                                          ┌────────────────┐
                                                          │   RED           │
                                                          │   (idle/ready)  │
                                                          └───────┬────────┘
                                                                  │
                                              ┌───────────────────┤
                                              │                   │
                                      face detected          no face
                                              │                   │
                                              v                   v
                                      ┌──────────────┐   ┌──────────────┐
                                      │   GREEN       │   │   RED         │
                                      │   (tracking)  │   │   (idle)      │
                                      └──────┬───────┘   └──────────────┘
                                             │
                                     expression detected
                                             │
                                ┌────────────┼────────────┐
                                │            │            │
                                v            v            v
                         ┌──────────┐ ┌──────────┐ ┌──────────┐
                         │  GREEN    │ │  BLUE     │ │  YELLOW   │
                         │  (smile)  │ │(surprise) │ │ (eyebrow) │
                         └──────────┘ └──────────┘ └──────────┘

  Note: LED4 is active-low — LOW = ON, HIGH = OFF.
  Any color can be set programmatically via Bridge.call("set_rgb", "color").
  Supported: red, green, blue, yellow, cyan, magenta, white, off.
```

### 8. Overlay Rendering Order

Each frame draws layers in a specific order. The overlay preset controls which layers are visible.

```
  Canvas (cleared each frame)
  ─────────────────────────────────────
  Layer 0: Video frame (via cam element)
  ─────────────────────────────────────
  Layer 1: Face mesh tessellation         ◄── toggleable
  Layer 2: Face contour / jawline         ◄── toggleable
  Layer 3: Eye outline connections        ◄── toggleable
  Layer 4: Eyebrow connections            ◄── toggleable
  Layer 5: Lip connections                ◄── toggleable
  Layer 6: Face oval (outer contour)      ◄── toggleable
  Layer 7: Iris connections + pupil ring  ◄── toggleable
  Layer 8: Iris diameter measurement      ◄── always (when iris visible)
  Layer 9: Landmark dots (478 per face)   ◄── toggleable
  Layer 10: Emoji expression indicators   ◄── toggleable
  Layer 11: Blink flash (hot pink)        ◄── triggered on blink
  Layer 12: Face label ("Face N · 12s")   ◄── always
  ─────────────────────────────────────
  Layer 13: System stats overlay          ◄── always (top-right)
  Layer 14: HUD ticker (bottom-center)    ◄── always
  ─────────────────────────────────────

  Overlay Presets (from PRESETS object in code):
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ Preset              │ Mesh │ Outline │ Eyes │ Brows │ Lips │ Iris │Dots│Emoji│
  ├─────────────────────┼──────┼─────────┼──────┼───────┼──────┼──────┼────┼─────┤
  │ Full Mesh+Features  │  ✓   │    ✓    │  ✓   │   ✓   │  ✓   │  ✓   │ ✓  │  ✓  │
  │ Outline+Features    │  ✗   │    ✓    │  ✓   │   ✓   │  ✓   │  ✓   │ ✗  │  ✓  │
  │ Mesh Only           │  ✓   │    ✗    │  ✗   │   ✗   │  ✗   │  ✗   │ ✗  │  ✗  │
  │ Dots Only           │  ✗   │    ✗    │  ✗   │   ✗   │  ✗   │  ✗   │ ✓  │  ✗  │
  │ Minimal             │  ✗   │    ✓    │  ✗   │   ✗   │  ✗   │  ✓   │ ✗  │  ✗  │
  │ Outline+Emojis      │  ✗   │    ✓    │  ✗   │   ✗   │  ✓   │  ✗   │ ✗  │  ✓  │
  └──────────────────────────────────────────────────────────────────────────┘

  Note: Iris measurement and pupil diameter display are always active
  when the iris layer is enabled in the current preset.
```

### 9. Delegate Selection & Validation Flow

The face landmarker delegate (CPU vs GPU) is selected at load time and continuously validated to catch inference issues.

```
  ┌────────────────┐
  │   App Start     │
  └───────┬────────┘
          │
          v
  ┌────────────────────┐
  │ Try CPU delegate    │ ◄── preferred (always correct)
  │ (WASM inference)    │
  └───┬────────────┬───┘
      │            │
   SUCCESS       FAIL
      │            │
      v            v
  ┌──────────┐  ┌──────────────────┐
  │ CPU       │  │ Try GPU delegate  │
  │ loaded    │  │ (WebGL/Adreno)   │
  └────┬─────┘  └──┬──────────┬────┘
       │            │          │
       │         SUCCESS     FAIL
       │            │          │
       │            v          v
       │      ┌──────────┐  ┌─────────┐
       │      │ GPU       │  │ FATAL   │
       │      │ loaded    │  │ No      │
       │      └────┬─────┘  │ delegate│
       │           │        └─────────┘
       └─────┬─────┘
             │
             v
  ┌──────────────────────────┐
  │ UNTESTED                  │
  │ Waiting for first face... │
  └──────────┬───────────────┘
             │ first face detected
             v
  ┌──────────────────────────┐
  │ VALIDATING                │
  │ Run 6 sanity checks on    │
  │ each of next 5 frames:    │
  │  1. Count = 478           │
  │  2. Bounding box > 3%     │
  │  3. Out-of-bounds < 20    │
  │  4. Nose near center      │
  │  5. Eye separation 2-50%  │
  │  6. Forehead above chin   │
  └──────────┬───────────────┘
             │ 5 frames checked
             │
      ┌──────┴──────┐
      │             │
   >= 3 PASS     >= 3 FAIL
      │             │
      v             v
  ┌────────┐  ┌─────────────┐
  │ PASSED  │  │ FAILED       │
  └───┬────┘  │ Auto-switch  │
      │       │ delegate &   │
      │       │ reload model │
      │       └──────────────┘
      │
      │ continuous check every 60s
      v
  ┌───────────────────────┐
  │ Re-validate 5 frames   │
  │ If degraded: warn      │
  │ (no auto-switch)       │
  └───────────────────────┘
```

### 10. WebSocket Telemetry Flow

Face data flows from the browser to the MPU, which drives MCU hardware responses. Telemetry is throttled to prevent flooding.

```
  Browser (every 500ms when faces present)
  ──────────────────────────────────────────
  emit("face_data", {
    faces: 2,
    blinks: {left: 0.1, right: 0.1},
    expression: "smile",
    pupilL: 4.2,
    pupilR: 4.1,
    yaw: -5.3,
    pitch: 2.1
  })
        │
        │ WebSocket
        v
  MPU (python/main.py :: on_face_data)
  ──────────────────────────────────────────
  1. Parse JSON payload
  2. Update face_state dict:
     ├─ face_count, blink_l/r, expression
     ├─ pupil_l/r_mm, yaw, pitch
     └─ last_update timestamp
  3. Determine state transition:
     │
     ├─ No face → Face appeared (new detection)
     │   ├─ Bridge: flash_face(3)
     │   ├─ Bridge: show_face()
     │   └─ Bridge: set_rgb("green")
     │
     ├─ Face → Face (ongoing, expression changed)
     │   ├─ Bridge: show_expression(expr)
     │   └─ Bridge: set_rgb(expr_color)
     │
     └─ Face → No face (all faces lost)
         ├─ Bridge: show_no_face()
         └─ Bridge: set_rgb("red")
  4. Emit state_update to browser (optional)
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
| **Boot step 1** | Smiley face bitmap (1.2s splash) |
| **Boot step 2** | Boot icon bitmap (0.8s) |
| **Boot step 3** | RGB self-test (R→G→B, 300ms each) |
| **Boot step 4** | Checkmark bitmap (✓) after Bridge init |
| **Startup 1-3** | Smiley bitmap (on scroll_text calls from MPU) |
| **Waiting** | Smiley bitmap (on `"Face Demo Ready"` scroll_text call) |
| **Face detected (new)** | Rapid flash smiley 3x → hold smiley (+ buzzer beep if enabled) |
| **Face detected (ongoing)** | Smiley bitmap (or expression bitmap) |
| **Expression: smile** | Smiley face bitmap (mouth curve) |
| **Expression: surprise** | O-mouth + wide eyes bitmap |
| **Expression: eyebrow** | Raised eyebrows + neutral mouth |
| **No face** | X pattern |
| **Mode change** | Scrolls `"Mode: uno_q"` (programmatic only) |

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
| `set_device_mode` | `"uno_q"` (string) | Store mode string (no hardware change — programmatic/test use only) |
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

Core: App Lab SDK (`arduino.app_utils`, `arduino.app_bricks.web_ui`) + Python stdlib.

Optional (for on-device AI face detection):

| Package | Notes |
|---------|-------|
| `tflite-runtime` | TFLite inference engine — lightweight, runs on QRB2210 CPU/GPU |
| `numpy` | Array operations for model input/output |
| `opencv-python-headless` | Camera capture (`/dev/video0`) + image preprocessing |

These are **not required** — the app falls back to browser-only MediaPipe if they're absent.

For model compilation (dev machine only, not on the Uno Q):

| Package | Notes |
|---------|-------|
| `qai-hub` | Qualcomm AI Hub SDK — compile models for QRB2210 in the cloud |
| `qai_hub_models` | Pre-built model wrappers (face_det_lite, mediapipe_face, etc.) |
| `torch` | PyTorch — needed for model tracing before compilation |

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

## On-Device Face Detection (Qualcomm AI Hub)

The project supports **optional on-device face detection** via TFLite models compiled through [Qualcomm AI Hub](https://aihub.qualcomm.com/). When a `.tflite` model is present, the QRB2210 MPU runs face detection directly from the camera — bypassing the browser's MediaPipe WASM engine entirely.

### Architecture

```
Without AI Hub (default):
  Camera (browser) → MediaPipe WASM → JavaScript → WebSocket → MPU → Bridge → MCU

With AI Hub (on-device):
  Camera (v4l2) → TFLite (MPU) → face results ─┬→ Bridge → MCU (LED/RGB)
                                                 └→ WebSocket → Browser (overlay)
```

### Supported Models

| Model | ID | Size | Speed | License |
|-------|----|------|-------|---------|
| **Lightweight Face Detection** (recommended) | `face_det_lite` | ~965 KB (INT8) | ~194μs (S8E) | BSD-3-Clause |
| **MediaPipe Face Detection** | `mediapipe_face` | ~4 MB | ~0.6ms (S23) | Apache-2.0 |

### Quick Start

```bash
# 1. On your dev machine — compile model for QRB2210
pip install qai-hub qai_hub_models torch
qai-hub configure --api_token YOUR_TOKEN
python python/ai_hub_setup.py --compile --model face_det_lite --device QRB2210

# 2. Copy the .tflite file to the Uno Q
scp python/models/face_det_lite.tflite unoq:~/face-demo/python/models/

# 3. On the Uno Q — install runtime deps
pip install tflite-runtime numpy opencv-python-headless

# 4. Reboot the app — it auto-discovers the model
```

### Helper Script (`python/ai_hub_setup.py`)

| Command | What it does |
|---------|-------------|
| `--check` | System readiness check (deps, auth, devices, existing models) |
| `--list` | List supported models with status |
| `--compile --model face_det_lite` | Compile via AI Hub cloud → download `.tflite` |
| `--compile --quantize w8a8` | Compile with INT8 quantization (smaller, faster) |
| `--download --model face_det_lite` | Download pre-built model (if available) |
| `--verify models/face_det_lite.tflite` | Load, inspect, and test-run a model file |

### Graceful Degradation

The system always works without AI Hub models. Every component is optional:

| Missing | Behavior |
|---------|----------|
| No `.tflite` model | Browser-only mode (MediaPipe WASM) |
| No `tflite-runtime` | Browser-only mode |
| No `opencv-python-headless` | Browser-only mode |
| No camera (`/dev/video*`) | Model loaded but no capture — browser still works |
| Model load fails | Error logged, browser-only mode |

Boot diagnostics report the full AI Hub status in the `AI HUB — ON-DEVICE FACE DETECTION` section.

### WebSocket Events (AI Hub)

| Event | Direction | Payload |
|-------|-----------|---------|
| `mpu_face_data` | MPU → Browser | `{faces, source:"mpu", inference_ms, detections:[{box, score}]}` |
| `ai_status_request` | Browser → MPU | `{}` (trigger status response) |
| `ai_status` | MPU → Browser | `{available, status, model, running, fps, inference_ms, ...}` |
| `ai_toggle` | Browser → MPU | `{enable: true/false}` (start/stop on-device detection) |

### QRB2210 Performance Notes

The QRB2210 is a quad-core Cortex-A53 @ 2.0 GHz with an Adreno GPU but **no Hexagon NPU**. TFLite runs on CPU/GPU. Expected performance:
- `face_det_lite` (INT8): ~5-15ms per frame (CPU), ~60-100 FPS theoretical
- `mediapipe_face`: ~10-25ms per frame (CPU), ~40-100 FPS theoretical
- Camera capture at 640x480 @ 15 FPS is the practical bottleneck

For NPU-accelerated inference, consider the QCS6490 or QCS8550 (higher-tier boards with Hexagon HTP).

## Reference Projects & Learnings

This project was informed by two key reference implementations that demonstrate working Uno Q patterns:

### DIY-ECG (diy-ecg-uno-Q)

A real-time ECG acquisition and visualization system. Three-layer architecture matching our own:

```
  MCU (STM32U585)                MPU (QRB2210)               Browser (WebUI)
  ──────────────                 ─────────────                ───────────────
  ADC sampling at 200Hz          Bridge.call("ecg_get_frame") Socket.IO client
  Ring buffer (200 samples)      IIR filters (HP/LP/notch)    WebGL plot (webgl-plot)
  k_timer for precise timing     Adaptive mean + BPM detect   Ring buffer (2000 samples)
  MsgPack binary frames          Delta payloads via WebSocket  CSV export
  CRC-16/IBM validation          Threading with RLock          Auto-scaling Y axis
```

**Key patterns borrowed/validated:**

| Pattern | ECG Implementation | Our Implementation |
|---------|-------------------|-------------------|
| Bridge RPC | `Bridge.provide("ecg_get_frame", handler)` returns `MsgPack::bin_t<uint8_t>` | `Bridge.provide("show_face", showFace)` (no params, reads global state) |
| Zephyr timing | `k_timer_init()` + `atomic_t` for 200Hz sampling | `delay()` based (no high-freq sampling needed) |
| WebUI Brick | `WebUI(assets_dir_path=...)` + `ui.on_message()`/`ui.send_message()` | Same pattern in `python/main.py` |
| Error resilience | `try/except` around `Bridge.call()` with reconnect | `safe_bridge_call()` wrapper, never crashes |
| Data flow | MCU→MPU poll (50ms) → MPU→Browser delta WS | Browser→MPU face telemetry (500ms) → MPU→MCU Bridge |
| Ring buffers | Both MCU and MPU circular buffers | Browser-side `trackedFaces` array with TTL |

**Noteworthy ECG techniques we could adopt:**
- Binary frame protocol with CRC validation for reliable Bridge data transfer
- Zephyr `k_timer` + `atomic_t` for interrupt-safe timing (vs `delay()`)
- IIR filter implementation in pure Python (no numpy dependency)
- WebGL rendering for high-performance real-time charts

### Arduino Uno Q Projects (community collection)

A comprehensive reference covering GenAI, peripherals, GPIO, debugging, and application development:

```
  ┌─────────────────────────────────────────────────────────┐
  │  Arduino Uno Q Projects — Key Modules                   │
  ├─────────────────────────────────────────────────────────┤
  │  01. GenAI Support                                      │
  │      ├─ Ollama local LLMs on QRB2210                   │
  │      ├─ OpenAI API integration                         │
  │      └─ Nanobot agent framework                        │
  │  02. Peripheral Hardware                                │
  │      ├─ WebCam via v4l2 + FFmpeg UDP streaming         │
  │      └─ SPI OLED display (ST7789 driver)               │
  │  03. Technical Setups                                   │
  │      ├─ GPIO via Zephyr Devicetree                     │
  │      │   └─ gpio_dt_spec + GPIO_DT_SPEC_GET_BY_IDX    │
  │      └─ Servo control via Bridge                       │
  │  04. Debugging                                          │
  │      ├─ FTDI debug interface for STM32U585             │
  │      └─ OpenOCD + VSCode debugging                     │
  │  05. Application Development                            │
  │      └─ OpenAI FaceInterpretor                         │
  │          ├─ MediaPipe face mesh → landmark JSON         │
  │          ├─ GPT-4o-mini vision analysis                │
  │          ├─ Podman container for Python 3.12            │
  │          ├─ MJPEG HTTP stream                          │
  │          └─ SPI display output via Bridge              │
  │  10. Tips & Tricks                                      │
  │      ├─ LED matrix flickering fix (Zephyr boot state)  │
  │      ├─ pyenv virtualenv for Python versions           │
  │      └─ STM32U585 firmware restore procedure           │
  └─────────────────────────────────────────────────────────┘
```

**Key patterns borrowed/validated:**

| Pattern | Reference Implementation | Our Implementation |
|---------|------------------------|-------------------|
| GPIO via Devicetree | `GPIO_DT_SPEC_GET_BY_IDX(USER_NODE, digital_pin_gpios, N)` | `digitalWrite(PIN, state)` (Arduino abstraction) |
| Bridge String params | `Bridge.provide("display_print", printFromPython)` with `String text` | `Bridge.provide("scroll_text", scrollText)` with `String text` |
| SPI display driver | Custom ST7789 with 5x7 bitmap font + word wrapping | LED matrix via `Arduino_LED_Matrix` + grayscale frames (simpler API, no ArduinoGraphics) |
| MediaPipe on-device | Python 3.12 in Podman, `cv2.VideoCapture("/dev/video2")` | Browser-side WASM (no container needed) |
| AI integration | GPT-4o-mini with threaded worker + processing lock | Expression detection via blendshapes (no LLM) |
| Camera access | `v4l2-ctl --list-devices`, `/dev/video2` | Browser `getUserMedia()` (USB webcam) |

**Critical Zephyr/hardware learnings documented in reference:**

1. **LED matrix flickering at boot** — STM32 data lines are undefined before sketch loads; random pixel noise is normal until firmware initializes the matrix
2. **GPIO mapping is NOT static** — Pins are resolved via Zephyr Devicetree at compile time, not hardcoded integers. `gpio_dt_spec` contains port controller + pin + flags
3. **Python version conflicts** — MediaPipe requires Python 3.12; Debian image ships 3.13. Solution: Podman containers or pyenv virtualenv
4. **LLM response time** — Local Ollama models on QRB2210 take ~90 seconds per response. Design for async "slow brain" patterns
5. **Camera streaming** — FFmpeg with `libx264 baseline` profile + `zerolatency` tuning gives lowest latency for UDP streaming
6. **SPI display** — ST7789 via raw SPI at 10MHz works reliably; custom 5x7 font bitmaps in PROGMEM

### Data Flow Comparison (All Three Projects)

```
  ┌────────────────────────────────────────────────────────────────────┐
  │                    DATA FLOW PATTERNS                              │
  ├────────────────────────────────────────────────────────────────────┤
  │                                                                    │
  │  Face Demo (this project):                                         │
  │    Camera → Browser WASM → Canvas overlay                          │
  │                         └→ WS → MPU → Bridge → MCU (LED/RGB)      │
  │    Direction: Browser-first, push to hardware                      │
  │                                                                    │
  │  DIY-ECG:                                                          │
  │    Sensor → MCU ADC → Ring buffer → Bridge RPC ← MPU poll          │
  │                                                   └→ WS → Browser  │
  │    Direction: Hardware-first, pull to browser                       │
  │                                                                    │
  │  FaceInterpretor:                                                  │
  │    Camera → Podman (MediaPipe + OpenAI) → HTTP API ← MPU poll      │
  │                                                      └→ Bridge     │
  │                                                         → MCU     │
  │                                                           (SPI)    │
  │    Direction: Container-first, bridge to display                    │
  │                                                                    │
  └────────────────────────────────────────────────────────────────────┘
```

## Credits

- [Arduino App Lab](https://docs.arduino.cc/software/app-lab/)
- [Arduino App Bricks](https://github.com/arduino/app-bricks-py)
- [Arduino App Bricks Examples](https://github.com/arduino/app-bricks-examples)
- [Google MediaPipe](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker)
- [Qualcomm AI Hub](https://aihub.qualcomm.com/)
- Qualcomm QRB2210 Dragonwing SoC
- [DIY-ECG Uno Q](https://github.com/diy-ecg/diy-ecg-uno-Q) — ECG acquisition reference
- [Arduino Uno Q Projects](https://github.com/MartinsRepo/Arduino-Uno-Q-Projects) — Community reference collection
