<div align="center">

# Wojo's Uno Q Face Outline Demo

### Real-Time Face Tracking on the Arduino Uno Q

<br/>

[![Arduino](https://img.shields.io/badge/Arduino-Uno_Q-00878F?style=for-the-badge&logo=arduino&logoColor=white)](https://docs.arduino.cc/hardware/uno-q/)
[![Qualcomm](https://img.shields.io/badge/Qualcomm-QRB2210-3253DC?style=for-the-badge&logo=qualcomm&logoColor=white)](https://www.qualcomm.com/products/technology/processors)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-Face_Landmarker-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker)
[![App Lab](https://img.shields.io/badge/App_Lab-Bricks_SDK-00878F?style=for-the-badge&logo=arduino&logoColor=white)](https://docs.arduino.cc/software/app-lab/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

<br/>

**478-point face landmarks &nbsp;|&nbsp; Up to 4 simultaneous faces &nbsp;|&nbsp; Expression detection &nbsp;|&nbsp; LED matrix feedback**

<br/>

A dual-processor edge AI demo built for the [Arduino Uno Q](https://docs.arduino.cc/hardware/uno-q/) --
Qualcomm QRB2210 + STM32U585 working together through
[Arduino App Lab](https://docs.arduino.cc/software/app-lab/) and the
[Bricks SDK](https://docs.arduino.cc/software/app-lab/tutorials/bricks).

</div>

<br/>

---

<br/>

## Table of Contents

1. [Why the Arduino Uno Q](#why-the-arduino-uno-q)
2. [Features at a Glance](#features-at-a-glance)
3. [Architecture](#architecture)
4. [Quick Start](#quick-start)
5. [Project Structure](#project-structure)
6. [State Diagrams](#state-diagrams)
7. [Performance](#performance)
8. [GPIO Placeholders](#gpio-placeholders)
9. [WebSocket Events](#websocket-events)
10. [Dependencies](#dependencies)
11. [Advanced Topics](#advanced-topics)
12. [Links & Resources](#links--resources)
13. [Contributing](#contributing)
14. [License](#license)

<br/>

---

<br/>

## Why the Arduino Uno Q

The [Arduino Uno Q](https://docs.arduino.cc/hardware/uno-q/) is **not a typical Arduino**.
It is a single-board computer with an embedded MCU, designed for AI at the edge.

<br/>

<p align="center">
  <img src="https://docs.arduino.cc/static/567189fab6cc1a00404d38e37b42e755/a6d36/uno-q-architecture-3.png" alt="UNO Q board architecture" width="700">
</p>

<br/>

| Component   | Silicon              | Key Specs                                                                          |
|:------------|:---------------------|:-----------------------------------------------------------------------------------|
| **MPU**     | Qualcomm QRB2210     | Quad-core Cortex-A53 @ 2.0 GHz, Adreno 702 GPU, Wi-Fi 5, BT 5.1, 2/4 GB LPDDR4   |
| **MCU**     | STM32U585            | Cortex-M33 @ 160 MHz, 2 MB flash, 786 KB SRAM, Zephyr RTOS                        |
| **Bridge**  | Arduino Bridge RPC   | Built-in serial link between MPU and MCU -- no wiring needed                       |

<br/>

The two processors communicate through a built-in RPC library called **Arduino Bridge**.
This demo exercises the full pipeline: browser-side AI inference, WebSocket telemetry to a
Python coordinator on Debian, Bridge RPC forwarding to the STM32 MCU, and physical feedback
through the built-in 13x8 LED matrix and RGB LED.

<br/>

<p align="center">
  <img src="https://docs.arduino.cc/static/c4c115ced208022ab43299bda7ea661e/a6d36/Simple-pinout-ABX00162.png" alt="UNO Q pinout" width="600">
</p>

<br/>

> **Tip:** For full pinout details, datasheet, schematics, and CAD files, see the
> [official hardware page](https://docs.arduino.cc/hardware/uno-q/) and the
> [UNO Q User Manual](https://docs.arduino.cc/tutorials/uno-q/user-manual/).

<br/>

---

<br/>

## Features at a Glance

| Feature                        | Description                                                                                                |
|:-------------------------------|:-----------------------------------------------------------------------------------------------------------|
| **478-Point Face Landmarks**   | Google MediaPipe Face Landmarker running in-browser via WASM -- zero setup, no model compilation            |
| **Multi-Face Tracking**        | Up to **4 simultaneous faces** with persistent IDs, unique colors, and 800ms TTL grace period              |
| **Expression Detection**       | Smile, surprise, eyebrow raise -- mapped to color-coded RGB LED feedback on the MCU                        |
| **Blink & Pupil Tracking**     | Eye Aspect Ratio (EAR) blink detection + iris diameter measurement in real time                            |
| **LED Matrix Visualization**   | 13x8 grayscale bitmaps: smiley (face detected), X (no face), expression icons, IP scroll on boot          |
| **Adaptive Performance**       | Auto-throttles frame processing when FPS drops below 8; recovers when FPS exceeds 14                      |
| **Swappable AI Source**        | Architecture decouples inference from actuation -- swap MediaPipe for App Lab Bricks, AI Hub, or Edge Impulse |
| **Full Boot Diagnostics**      | CPU, RAM, network, DNS, CDN reachability checks printed to terminal on every startup                       |
| **Bridge RPC Handshake**       | MCU retries `mcu_ready` every 3s for up to 3 minutes; MPU acknowledges from a background thread            |
| **GPIO Expansion Ready**       | 5 pre-configured pins (D3-D7) for relay, buzzer, NeoPixel, or Modulino accessories                        |

<br/>

---

<br/>

## Architecture

### System Overview

<br/>

<p align="center">
  <img src="https://mermaid.ink/img/Z3JhcGggVEQKICAgIHN1YmdyYXBoIEJyb3dzZXJbIkJyb3dzZXIgKFdlYlVJIEJyaWNrKSAtLSBhc3NldHMvaW5kZXguaHRtbCJdCiAgICAgICAgTVBbIk1lZGlhUGlwZSBGYWNlIExhbmRtYXJrZXIgKFdBU00pPGJyLz40NzggbGFuZG1hcmtzLCA0IGZhY2VzIG1heCJdCiAgICAgICAgQ09bIkNhbnZhcyBvdmVybGF5PGJyLz5tZXNoLCBvdXRsaW5lLCBpcmlzLCBIVUQsIGVtb2ppcyJdCiAgICAgICAgQVBbIkFkYXB0aXZlIHBlcmZvcm1hbmNlPGJyLz5hdXRvLXNraXAgZnJhbWVzIHdoZW4gRlBTIDwgOCJdCiAgICAgICAgV1NfT1VUWyJXZWJTb2NrZXQgdGVsZW1ldHJ5PGJyLz5mYWNlX2RhdGEsIHJnYl9jb250cm9sLCBncGlvX2NvbnRyb2wiXQogICAgZW5kCgogICAgc3ViZ3JhcGggTVBVWyJMaW51eCBNUFUgKFFSQjIyMTApIC0tIHB5dGhvbi9tYWluLnB5Il0KICAgICAgICBXQlsiV2ViVUkgQnJpY2s8YnIvPnNlcnZlcyBhc3NldHMvICsgV2ViU29ja2V0Il0KICAgICAgICBCRFsiQm9vdCBkaWFnbm9zdGljczxici8-Q1BVLCBSQU0sIG5ldHdvcmssIEROUywgQ0ROIl0KICAgICAgICBCRlsiQnJpZGdlLmNhbGwgZm9yd2FyZGluZzxici8-ZmFjZSBzdGF0ZSB0byBNQ1UgaGFyZHdhcmUiXQogICAgICAgIEFIWyJBSSBIdWIgZmFsbGJhY2s8YnIvPm9wdGlvbmFsIFRGTGl0ZSBvbi1kZXZpY2UiXQogICAgZW5kCgogICAgc3ViZ3JhcGggTUNVWyJTVE0zMiBNQ1UgKFNUTTMyVTU4NSkgLS0gc2tldGNoL3NrZXRjaC5pbm8iXQogICAgICAgIExFRFsiMTN4OCBMRUQgbWF0cml4PGJyLz5ncmF5c2NhbGUgYml0bWFwcyJdCiAgICAgICAgUkdCWyJSR0IgTEVEIChMRUQ0LCBhY3RpdmUtbG93KTxici8-c3RhdHVzICsgZXhwcmVzc2lvbiBjb2xvcnMiXQogICAgICAgIFNMWyJTdGF0dXMgTEVEIChMRURfQlVJTFRJTik8YnIvPnNvbGlkID0gZmFjZSBwcmVzZW50Il0KICAgICAgICBHUElPWyJHUElPIHBsYWNlaG9sZGVycyBEMy1ENzxici8-cmVsYXksIGJ1enplciwgTmVvUGl4ZWwiXQogICAgICAgIEJQWyIxMCBCcmlkZ2UgcHJvdmlkZXJzPGJyLz5ldmVudC1kcml2ZW4sIGxvb3AgaGFuZGxlcyByZXRyeS90aW1lb3V0Il0KICAgIGVuZAoKICAgIEJyb3dzZXIgLS0-fCJXZWJTb2NrZXQgKEpTT04sIHRocm90dGxlZCA1MDBtcyk8YnIvPmluamVjdGVkIGJ5IEJyaWNrIFNESyBhdCBydW50aW1lInwgTVBVCiAgICBNUFUgLS0-fCJCcmlkZ2UgUlBDPGJyLz4oQXJkdWlub19Sb3V0ZXJCcmlkZ2UpInwgTUNV?type=png&bgColor=!white" alt="diagram" width="700">
</p>

<details>
<summary>Diagram source (Mermaid)</summary>

```mermaid
graph TD
    subgraph Browser["Browser (WebUI Brick) -- assets/index.html"]
        MP["MediaPipe Face Landmarker (WASM)<br/>478 landmarks, 4 faces max"]
        CO["Canvas overlay<br/>mesh, outline, iris, HUD, emojis"]
        AP["Adaptive performance<br/>auto-skip frames when FPS < 8"]
        WS_OUT["WebSocket telemetry<br/>face_data, rgb_control, gpio_control"]
    end

    subgraph MPU["Linux MPU (QRB2210) -- python/main.py"]
        WB["WebUI Brick<br/>serves assets/ + WebSocket"]
        BD["Boot diagnostics<br/>CPU, RAM, network, DNS, CDN"]
        BF["Bridge.call forwarding<br/>face state to MCU hardware"]
        AH["AI Hub fallback<br/>optional TFLite on-device"]
    end

    subgraph MCU["STM32 MCU (STM32U585) -- sketch/sketch.ino"]
        LED["13x8 LED matrix<br/>grayscale bitmaps"]
        RGB["RGB LED (LED4, active-low)<br/>status + expression colors"]
        SL["Status LED (LED_BUILTIN)<br/>solid = face present"]
        GPIO["GPIO placeholders D3-D7<br/>relay, buzzer, NeoPixel"]
        BP["10 Bridge providers<br/>event-driven, loop handles retry/timeout"]
    end

    Browser -->|"WebSocket (JSON, throttled 500ms)<br/>injected by Brick SDK at runtime"| MPU
    MPU -->|"Bridge RPC<br/>(Arduino_RouterBridge)"| MCU
```

</details>

<br/>

### Data Flow Pipeline

<br/>

<p align="center">
  <img src="https://mermaid.ink/img/Z3JhcGggTFIKICAgIEFbIlVTQiBXZWJjYW08YnIvPihVVkMsIDY0MHg0ODApIl0gLS0-fCJWaWRlbyBmcmFtZXMifCBCWyJCcm93c2VyPGJyLz4oTWVkaWFQaXBlIFdBU00pIl0KICAgIEIgLS0-fCJXZWJTb2NrZXQ8YnIvPihKU09OLCA1MDBtcykifCBDWyJQeXRob24gb24gRGViaWFuPGJyLz4obWFpbi5weSkiXQogICAgQyAtLT58IkJyaWRnZSBSUEMifCBEWyJTVE0zMiBNQ1U8YnIvPihza2V0Y2guaW5vKSJdCiAgICBCIC0uLT58IkFJIGluZmVyZW5jZTxici8-NDc4IGxhbmRtYXJrcyJ8IEIKICAgIEMgLS4tPnwiQ29vcmRpbmF0ZXM8YnIvPmRhdGEgZmxvdyJ8IEMKICAgIEQgLS4tPnwiTEVEIG1hdHJpeCwgUkdCLDxici8-R1BJTyBjb250cm9sInwgRA==?type=png&bgColor=!white" alt="diagram" width="700">
</p>

<details>
<summary>Diagram source (Mermaid)</summary>

```mermaid
graph LR
    A["USB Webcam<br/>(UVC, 640x480)"] -->|"Video frames"| B["Browser<br/>(MediaPipe WASM)"]
    B -->|"WebSocket<br/>(JSON, 500ms)"| C["Python on Debian<br/>(main.py)"]
    C -->|"Bridge RPC"| D["STM32 MCU<br/>(sketch.ino)"]
    B -.->|"AI inference<br/>478 landmarks"| B
    C -.->|"Coordinates<br/>data flow"| C
    D -.->|"LED matrix, RGB,<br/>GPIO control"| D
```

</details>

<br/>

### Compute Architecture

The Uno Q has **four distinct compute blocks**:

<br/>

<p align="center">
  <img src="https://www.qualcomm.com/content/dam/qcomm-martech/dm-assets/images/pdp/block_diagram/image/QRB2210-diagram.svg" alt="QRB2210 block diagram" width="600">
</p>

<br/>

| Block    | Silicon                           | Clock     | Role in This Demo                                                                                     |
|:---------|:----------------------------------|:----------|:------------------------------------------------------------------------------------------------------|
| **CPU**  | Quad-core Arm Cortex-A53 (Kryo)   | 2.0 GHz   | Runs Debian Linux, Python coordinator, Docker containers for App Lab Bricks, and the Chromium browser  |
| **GPU**  | Qualcomm Adreno 702               | 845 MHz   | OpenGL ES 3.1, Vulkan 1.1, OpenCL 2.0 -- available for WebGL rendering and TFLite GPU delegate        |
| **DSP**  | Dual-core Qualcomm Hexagon        | --        | Audio signal processing and always-on low-power tasks. *Not used by this demo*                         |
| **MCU**  | STM32U585 Arm Cortex-M33          | 160 MHz   | Runs Arduino sketch on Zephyr OS -- drives LED matrix, RGB LED, status LED, and GPIO                   |

<br/>

> **Architecture Note:** The QRB2210 has **no dedicated TPU or NPU** (no TOPS rating).
> AI inference relies on the CPU and GPU through framework runtimes like TFLite and WASM.
> This is an intentional tradeoff -- the QRB2210 is Qualcomm's entry-tier IoT processor,
> optimized for low power and cost. For NPU-accelerated inference, Qualcomm's higher-tier
> processors (QCS6490, QCS8550) include the Hexagon Tensor Processor.

<br/>

### App Lab Bricks

The `arduino:web_ui` Brick powers this demo. It serves HTML/JS from `assets/`, provides
WebSocket messaging between the browser and Python, and requires **zero configuration**
beyond one line in `app.yaml`.

<br/>

| Brick                          | What It Does                                  | Setup                               |
|:-------------------------------|:----------------------------------------------|:------------------------------------|
| **`arduino:web_ui`**           | Serves web content + WebSocket                | **This demo uses it**               |
| `arduino:object_detection`     | Detects objects in camera frames (YOLOX-Nano)  | Add one line to `app.yaml`          |
| `arduino:motion_detection`     | Detects motion in video stream                | Add one line to `app.yaml`          |

<br/>

```yaml
bricks:
  - arduino:web_ui
  - arduino:object_detection   # optional -- add any Brick with one line
```

<br/>

> **Tip:** Each Brick deploys as a container on the QRB2210 and exposes an API
> to your Python code. No Docker configuration required.

<br/>

---

<br/>

## Quick Start

### Hardware Requirements

| Component       | Details                                                                                                      |
|:----------------|:-------------------------------------------------------------------------------------------------------------|
| **Board**       | [Arduino Uno Q](https://store.arduino.cc/pages/uno-q) (QRB2210 + STM32U585, 2 GB or 4 GB)                   |
| **LED Matrix**  | Built-in 13x8 (no wiring needed)                                                                             |
| **Camera**      | Standard UVC USB webcam                                                                                       |
| **Connection**  | [USB-C multiport adapter](https://store.arduino.cc/products/usb-c-to-hdmi-multiport-adapter-with-ethernet-and-usb-hub) with external power delivery |
| **Browser**     | Chrome or Edge on any device on the same network                                                              |

<br/>

The board can be powered via USB-C (5V 3A), the 5V pin, or VIN (7-24V):

<br/>

<p align="center">
  <img src="https://docs.arduino.cc/static/72456f6873252eb705cfd28538166e8a/a6d36/power-options-3.png" alt="UNO Q power options" width="500">
</p>

<br/>

### Installation

App Lab runs in two modes: **directly on the Uno Q** as a single-board computer
(SBC mode, recommended with the 4 GB variant), or **hosted on your PC** with the
board connected via USB-C.

<br/>

<p align="center">
  <img src="https://docs.arduino.cc/static/a149a5e406178f25376d784b1d615e6d/a6d36/modes-2.png" alt="SBC and PC hosted modes" width="600">
</p>

<br/>

**Get running in five steps:**

1. **Download** this repository as a `.zip` file.

2. **Open** [Arduino App Lab](https://www.arduino.cc/en/software/#app-lab-section) --
   pre-installed on the Uno Q in SBC mode, or install the desktop version on your PC.

3. **Import** -- click **Import App** and select the `.zip` file.

4. **Wait** -- App Lab reads `app.yaml`, compiles the sketch for the STM32 MCU,
   deploys the WebUI Brick, and launches the application automatically.

5. **Connect** -- the LED matrix will display the board's IP address.
   Open that address in Chrome on any device on the same Wi-Fi network.

<br/>

> **Quick SSH setup (yzma style):** If you prefer the terminal over App Lab,
> this project supports a direct-run workflow inspired by the
> [yzma LLM project](https://projecthub.arduino.cc/marc-edgeimpulse/running-local-llms-and-vlms-on-the-arduino-uno-q-with-yzma-74e288):
>
> ```bash
> ssh arduino@<IP>
> git clone https://github.com/wojo/face-tracker-uno-q && cd face-tracker-uno-q
> ./setup.sh                        # installs deps + downloads face detection models
> python3 direct/face_tracker.py    # standalone face tracking (no App Lab needed)
> ```
>
> Or download individual models yzma-style:
> ```bash
> ./model_get.sh --list                     # see available models
> ./model_get.sh face-detection             # download YuNet face detector (233 KB)
> ./model_get.sh face-mesh                  # download 468-landmark mesh model
> ./model_get.sh -u <huggingface_url>       # download any custom ONNX model
> ```
>
> The standalone tracker uses OpenCV YuNet (75K params) for face detection and
> optionally ONNX Runtime for 468-landmark face mesh -- all running natively on
> the Cortex-A53. MCU LED matrix and RGB LED are controlled via the system-level
> `arduino-router` Bridge service (no App Lab required).

<br/>

### First-Time Setup on a Fresh Board

If this is a brand-new Uno Q that has never been connected to App Lab before,
expect several update prompts before the demo runs.

<br/>

<details>
<summary><strong>What App Lab will prompt you to update</strong></summary>

<br/>

| Prompt                             | What It Updates                                    | Action       | What Happens If You Skip                          |
|:-----------------------------------|:---------------------------------------------------|:-------------|:--------------------------------------------------|
| System firmware                    | Linux OS image on the QRB2210 MPU                  | **Accept**   | Risk kernel/driver incompatibilities              |
| Arduino board core (Zephyr)        | Zephyr RTOS platform for STM32 MCU sketches        | **Accept**   | Sketch compilation will likely fail               |
| Board firmware (STM32 bootloader)  | Low-level MCU bootloader                           | **Accept**   | `Bridge.begin()` may hang or fail silently        |
| Brick container updates            | Docker images for WebUI Brick and App Lab services | **Accept**   | Demo cannot start without the WebUI Brick         |

<br/>

</details>

<br/>

**After accepting all updates:**

1. **Wait for reboot.** The board may reboot more than once. Wait for the green
   power LED to stabilize -- this can take **60-90 seconds** on first boot
   after a firmware update.

2. **Connect to Wi-Fi** if not already configured via **App Lab > Settings > Network**.
   The demo needs internet access to download MediaPipe (~4 MB) from
   `cdn.jsdelivr.net` on first load. After that, the browser caches everything.

3. **Import the demo** `.zip` and let App Lab compile the sketch (~30-60 seconds).
   The LED matrix will show a boot icon, then a checkmark, then scroll the
   board's IP address.

4. **Open the IP address** in Chrome on any device on the same Wi-Fi network.

<br/>

### Troubleshooting

<details>
<summary><strong>Common issues and fixes</strong></summary>

<br/>

| Symptom                                         | Likely Cause                               | Fix                                                                                      |
|:-------------------------------------------------|:-------------------------------------------|:-----------------------------------------------------------------------------------------|
| Blank screen, no error                           | JavaScript module failed to load           | Open browser console (F12), check network errors -- usually `cdn.jsdelivr.net` unreachable |
| "Cannot Load Face Detection Engine" overlay      | No internet                                | Connect to Wi-Fi and hit the Retry button                                                |
| LED matrix stays on boot icon                    | `Bridge.begin()` stuck (firmware mismatch) | Accept all pending updates in App Lab, re-import                                         |
| "No Camera Detected" overlay                     | No USB webcam plugged in                   | Plug a USB webcam into any USB-A port (MIPI-CSI requires Media Carrier)                  |
| Camera permission denied                         | Browser blocking camera access             | Check browser settings > Site permissions > Camera > Allow                                |
| MCU shows red LED, Python says "MCU ready"       | Normal behavior                            | MCU starts red (idle) -- turns green when first face is detected                         |
| Sketch won't compile                             | Outdated board core                        | Ensure `arduino:zephyr` is installed and up to date                                      |

<br/>

</details>

<br/>

<details>
<summary><strong>Recovery if you declined updates</strong></summary>

<br/>

If you said "No" to one or more update prompts and the demo doesn't work:

1. Open App Lab settings
2. Check for board/firmware/core updates
3. Accept all pending updates
4. Reboot the board
5. Re-import the demo `.zip`

<br/>

> **Note:** The MCU sketch includes an acknowledgement-driven retry mechanism --
> it re-sends `mcu_ready` every 3 seconds for up to 3 minutes after boot. Once the
> MPU receives the signal, it dispatches `mpu_ack` from a background thread (to avoid
> deadlocking the Bridge read loop), and the MCU stops retrying.

<br/>

</details>

<br/>

---

<br/>

## Project Structure

```
.
├── app.yaml                    # App Lab manifest (bricks: arduino:web_ui)
│
├── python/
│   ├── main.py                 # MPU coordinator -- WebUI Brick + Bridge forwarding
│   ├── face_detector_mpu.py    # On-device TFLite face detection wrapper
│   ├── ai_hub_setup.py         # AI Hub model download/compile helper
│   ├── requirements.txt        # Python runtime dependencies
│   └── models/                 # .tflite model files (auto-discovered at boot)
│
├── sketch/
│   ├── sketch.ino              # MCU firmware -- Bridge.provide() + LED matrix
│   └── sketch.yaml             # Arduino CLI board profile and library versions
│
├── assets/                     # Frontend (served by WebUI Brick on device)
│   ├── index.html              # Face tracking UI
│   ├── css/styles.css          # Stylesheet
│   ├── js/app.js               # Application logic (ES module)
│   └── qualcomm-logo.png       # Branding asset
│
├── app.py                      # Replit-only Flask dev server (not in App Lab zip)
├── templates/                  # Replit copy of assets/ (kept in sync)
└── static/                     # Replit static assets
```

<br/>

---

<br/>

## State Diagrams

### 1. Full System Boot Sequence

Both processors boot in parallel. The MCU completes first (no OS) and waits
for Bridge; the MPU runs Linux, starts Python, then connects.

<br/>

<p align="center">
  <img src="https://mermaid.ink/img/c2VxdWVuY2VEaWFncmFtCiAgICBwYXJ0aWNpcGFudCBNQ1UgYXMgU1RNMzJVNTg1IE1DVQogICAgcGFydGljaXBhbnQgTVBVIGFzIFFSQjIyMTAgTVBVCgogICAgTm90ZSBvdmVyIE1DVTogUG93ZXItb24KICAgIE5vdGUgb3ZlciBNUFU6IFBvd2VyLW9uCgogICAgTUNVLT4-TUNVOiBTZXJpYWwuYmVnaW4oMTE1MjAwKQogICAgTUNVLT4-TUNVOiBQcmludCBiYW5uZXIgKyBzcGVjcwogICAgTUNVLT4-TUNVOiBDb25maWd1cmUgR1BJTyBwaW5zCiAgICBNQ1UtPj5NQ1U6IG1hdHJpeC5iZWdpbigpCiAgICBNQ1UtPj5NQ1U6IFNob3cgc21pbGV5IGJpdG1hcCAoMS4ycykKICAgIE1DVS0-Pk1DVTogU2hvdyBib290IGljb24gKDAuOHMpCiAgICBNUFUtPj5NUFU6IExpbnV4IGtlcm5lbCBib290CiAgICBNUFUtPj5NUFU6IFB5dGhvbiBydW50aW1lIHN0YXJ0CiAgICBNUFUtPj5NUFU6IEltcG9ydCBBcHAgTGFiIFNESwogICAgTUNVLT4-TUNVOiBSR0Igc2VsZi10ZXN0IChSL0cvQiwgMzAwbXMgZWFjaCkKICAgIE1QVS0-Pk1QVTogU3lzdGVtIGRpYWdub3N0aWNzIChDUFUsIFJBTSwgbmV0d29yaywgRE5TLCBDRE4pCiAgICBNQ1UtPj5NQ1U6IEJyaWRnZS5iZWdpbigpCiAgICBNQ1UtPj5NQ1U6IFJlZ2lzdGVyIDkgQnJpZGdlIHByb3ZpZGVycwogICAgTUNVLT4-TUNVOiBTaG93IGNoZWNrbWFyayBiaXRtYXAgKDAuOHMpCiAgICBNUFUtPj5NUFU6IEJyaWRnZS5iZWdpbigpCiAgICBNQ1UtPj5NUFU6IEJyaWRnZS5jYWxsKCJtY3VfcmVhZHkiKQogICAgTm90ZSBvdmVyIE1QVTogX2JyaWRnZV9yZWFkeSA9IFRydWUKICAgIE1DVS0-Pk1DVTogU2V0IFJHQiByZWQgKGlkbGUsIHdhaXRpbmcpCiAgICBNUFUtPj5NQ1U6IHNhZmVfYnJpZGdlX2NhbGwoInNjcm9sbF90ZXh0IiwgSVApCiAgICBOb3RlIG92ZXIgTUNVOiBTaG93IHNtaWxleSAoc2Nyb2xsX3RleHQgaGFuZGxlcikKICAgIE1QVS0-Pk1DVTogc2FmZV9icmlkZ2VfY2FsbCgic2Nyb2xsX3RleHQiLCBSQU0pCiAgICBNUFUtPj5NQ1U6IHNhZmVfYnJpZGdlX2NhbGwoInNjcm9sbF90ZXh0Iiwga2VybmVsKQogICAgTVBVLT4-TVBVOiBTdGFydCBXZWJVSSBCcmljayAoc2VydmUgYXNzZXRzLykKICAgIE1QVS0-Pk1DVTogc2FmZV9icmlkZ2VfY2FsbCgic2Nyb2xsX3RleHQiLCAiRmFjZSBEZW1vIFJlYWR5IikKICAgIE1QVS0-Pk1QVTogV2ViU29ja2V0IHNlcnZlciByZWFkeQogICAgTm90ZSBvdmVyIE1QVTogQk9PVCBDT01QTEVURQogICAgTm90ZSBvdmVyIE1DVTogSWRsZSAtIHdhaXRpbmcgZm9yIEJyaWRnZSBldmVudHMKICAgIE5vdGUgb3ZlciBNUFU6IElkbGUgLSB3YWl0aW5nIGZvciBXUy9CcmlkZ2U=?type=png&bgColor=!white" alt="diagram" width="700">
</p>

<details>
<summary>Diagram source (Mermaid)</summary>

```mermaid
sequenceDiagram
    participant MCU as STM32U585 MCU
    participant MPU as QRB2210 MPU

    Note over MCU: Power-on
    Note over MPU: Power-on

    MCU->>MCU: Serial.begin(115200)
    MCU->>MCU: Print banner + specs
    MCU->>MCU: Configure GPIO pins
    MCU->>MCU: matrix.begin()
    MCU->>MCU: Show smiley bitmap (1.2s)
    MCU->>MCU: Show boot icon (0.8s)
    MPU->>MPU: Linux kernel boot
    MPU->>MPU: Python runtime start
    MPU->>MPU: Import App Lab SDK
    MCU->>MCU: RGB self-test (R/G/B, 300ms each)
    MPU->>MPU: System diagnostics (CPU, RAM, network, DNS, CDN)
    MCU->>MCU: Bridge.begin()
    MCU->>MCU: Register 9 Bridge providers
    MCU->>MCU: Show checkmark bitmap (0.8s)
    MPU->>MPU: Bridge.begin()
    MCU->>MPU: Bridge.call("mcu_ready")
    Note over MPU: _bridge_ready = True
    MCU->>MCU: Set RGB red (idle, waiting)
    MPU->>MCU: safe_bridge_call("scroll_text", IP)
    Note over MCU: Show smiley (scroll_text handler)
    MPU->>MCU: safe_bridge_call("scroll_text", RAM)
    MPU->>MCU: safe_bridge_call("scroll_text", kernel)
    MPU->>MPU: Start WebUI Brick (serve assets/)
    MPU->>MCU: safe_bridge_call("scroll_text", "Face Demo Ready")
    MPU->>MPU: WebSocket server ready
    Note over MPU: BOOT COMPLETE
    Note over MCU: Idle - waiting for Bridge events
    Note over MPU: Idle - waiting for WS/Bridge
```

</details>

<br/>

> **Note:** The `scrollText` MCU handler currently displays `frame_smiley` rather
> than scrolling text -- text scrolling requires ArduinoGraphics font rendering
> which is not yet implemented for the Zephyr platform.

<br/>

### 2. Camera Initialization Flow

<br/>

<p align="center">
  <img src="https://mermaid.ink/img/Z3JhcGggVEQKICAgIEFbIlBhZ2UgTG9hZCJdIC0tPiBCWyJuYXZpZ2F0b3IubWVkaWFEZXZpY2VzLmdldFVzZXJNZWRpYSgpIl0KICAgIEIgLS0-fFNVQ0NFU1N8IENbIkdvdCBzdHJlYW0iXQogICAgQiAtLT58RVJST1J8IER7IkNoZWNrIGVycm9yIHR5cGUifQoKICAgIEQgLS0-fE5vdEFsbG93ZWRFcnJvcnwgRVsiUGVybWlzc2lvbiBkZW5pZWQiXQogICAgRCAtLT58Tm90Rm91bmRFcnJvcnwgRlsiTm8gY2FtZXJhIGZvdW5kIl0KICAgIEQgLS0-fE90aGVyfCBHWyJHZW5lcmljIGVycm9yIG1lc3NhZ2UiXQogICAgRSAtLT4gSFsiU2hvdyBjYW1lcmEtZXJyb3Igb3ZlcmxheTxici8-d2l0aCBmaXggaW5zdHJ1Y3Rpb25zIl0KICAgIEYgLS0-IEgKICAgIEcgLS0-IEgKCiAgICBDIC0tPiBJWyJHZXQgdHJhY2sgc2V0dGluZ3M8YnIvPmxhYmVsLCByZXNvbHV0aW9uLCBmcmFtZVJhdGUsPGJyLz5mYWNpbmdNb2RlLCBtZWdhcGl4ZWxzIl0KICAgIEkgLS0-IEpbImNhbS5zcmNPYmplY3QgPSBzdHJlYW0iXQogICAgSiAtLT58b25sb2FkZWRkYXRhfCBLWyJJbml0IEZhY2VMYW5kbWFya2VyIl0KICAgIEsgLS0-fG9uUmVhZHl8IExbIlN0YXJ0IGRyYXcoKSByZW5kZXIgbG9vcCJd?type=png&bgColor=!white" alt="diagram" width="700">
</p>

<details>
<summary>Diagram source (Mermaid)</summary>

```mermaid
graph TD
    A["Page Load"] --> B["navigator.mediaDevices.getUserMedia()"]
    B -->|SUCCESS| C["Got stream"]
    B -->|ERROR| D{"Check error type"}

    D -->|NotAllowedError| E["Permission denied"]
    D -->|NotFoundError| F["No camera found"]
    D -->|Other| G["Generic error message"]
    E --> H["Show camera-error overlay<br/>with fix instructions"]
    F --> H
    G --> H

    C --> I["Get track settings<br/>label, resolution, frameRate,<br/>facingMode, megapixels"]
    I --> J["cam.srcObject = stream"]
    J -->|onloadeddata| K["Init FaceLandmarker"]
    K -->|onReady| L["Start draw() render loop"]
```

</details>

<br/>

<details>
<summary><strong>3. Face Detection and Rendering Pipeline</strong></summary>

<br/>

Every animation frame passes through this pipeline. The adaptive performance
system may skip frames to maintain smooth rendering.

<br/>

<p align="center">
  <img src="https://mermaid.ink/img/Z3JhcGggVEQKICAgIEFbInJlcXVlc3RBbmltYXRpb25GcmFtZShkcmF3KSJdIC0tPiBCeyJjYW0gcGF1c2VkL2VuZGVkPGJyLz5vciBubyBtb2RlbD8ifQogICAgQiAtLT58WUVTfCBaMVsicmV0dXJuIChza2lwKSJdCiAgICBCIC0tPnxOT3wgQ3siU2FtZSB2aWRlbyBmcmFtZTxici8-YXMgbGFzdCB0aW1lPyJ9CiAgICBDIC0tPnxZRVN8IFoyWyJyZXR1cm4gKHNraXApIl0KICAgIEMgLS0-fE5PfCBEeyJza2lwRnJhbWVzID4gMDxici8-YW5kIG5vdCBvdXIgdHVybj8ifQogICAgRCAtLT58WUVTfCBaM1siaW5jcmVtZW50IGNvdW50ZXJzLCByZXR1cm4iXQogICAgRCAtLT58Tk98IEVbImZsLmRldGVjdEZvclZpZGVvKCk8YnIvPk1lZGlhUGlwZSBXQVNNIGluZmVyZW5jZTxici8-NDc4IGxhbmRtYXJrcyBwZXIgZmFjZSJdCiAgICBFIC0tPiBGWyJDYXAgZmFjZXMgdG8gTUFYX0ZBQ0VTICg0KSJdCiAgICBGIC0tPiBHWyJtYXRjaEZhY2VzKCk8YnIvPnNvcnRlZCBtaW4tZGlzdGFuY2UsPGJyLz5hZGFwdGl2ZSB0aHJlc2hvbGRzLDxici8-ODAwbXMgVFRMIHN1cnZpdm9ycyJdCiAgICBHIC0tPiBIWyJGb3IgZWFjaCBmYWNlOjxici8-bWVzaC9vdXRsaW5lLCBpcmlzLCBwdXBpbHMsPGJyLz5ibGlua3MgKEVBUiksIGV4cHJlc3Npb24sPGJyLz5lbW9qaXMsIGhlYWQgcG9zZSwgZG90cywgbGFiZWwiXQogICAgSCAtLT4gSVsiZHJhd1N5c092ZXJsYXkoKTxici8-Q1BVL1JBTS90ZW1wIHN0YXRzIl0KICAgIEkgLS0-IEpbInVwZGF0ZUFkYXB0aXZlUGVyZigpPGJyLz5jaGVjayBGUFMsIGFkanVzdCBza2lwIl0KICAgIEogLS0-IEtbIlVwZGF0ZSBIVUQgKGV2ZXJ5IDUwMG1zKTxici8-ZmFjZXMsIEZQUywgbGF0ZW5jeSwgcHVwaWxzLDxici8-YmxpbmtzLCB5YXcvcGl0Y2gsIHVwdGltZSJdCiAgICBLIC0tPiBMWyJFbWl0IGZhY2VfZGF0YSB2aWEgV2ViU29ja2V0PGJyLz50aHJvdHRsZWQgdG8gNTAwbXMiXQ==?type=png&bgColor=!white" alt="diagram" width="700">
</p>

<details>
<summary>Diagram source (Mermaid)</summary>

```mermaid
graph TD
    A["requestAnimationFrame(draw)"] --> B{"cam paused/ended<br/>or no model?"}
    B -->|YES| Z1["return (skip)"]
    B -->|NO| C{"Same video frame<br/>as last time?"}
    C -->|YES| Z2["return (skip)"]
    C -->|NO| D{"skipFrames > 0<br/>and not our turn?"}
    D -->|YES| Z3["increment counters, return"]
    D -->|NO| E["fl.detectForVideo()<br/>MediaPipe WASM inference<br/>478 landmarks per face"]
    E --> F["Cap faces to MAX_FACES (4)"]
    F --> G["matchFaces()<br/>sorted min-distance,<br/>adaptive thresholds,<br/>800ms TTL survivors"]
    G --> H["For each face:<br/>mesh/outline, iris, pupils,<br/>blinks (EAR), expression,<br/>emojis, head pose, dots, label"]
    H --> I["drawSysOverlay()<br/>CPU/RAM/temp stats"]
    I --> J["updateAdaptivePerf()<br/>check FPS, adjust skip"]
    J --> K["Update HUD (every 500ms)<br/>faces, FPS, latency, pupils,<br/>blinks, yaw/pitch, uptime"]
    K --> L["Emit face_data via WebSocket<br/>throttled to 500ms"]
```

</details>

<br/>

</details>

<br/>

<details>
<summary><strong>4. Adaptive Performance State Machine</strong></summary>

<br/>

Monitors FPS over a sliding window and auto-adjusts frame skipping.
Hysteresis gap (8 to 14) prevents rapid toggling.

<br/>

<p align="center">
  <img src="https://mermaid.ink/img/c3RhdGVEaWFncmFtLXYyCiAgICBbKl0gLS0-IE9QVElNQUwKICAgIE9QVElNQUwgLS0-IEFVVE9fVEhST1RUTEVEIDogYXZnIEZQUyA8IDggKG92ZXIgMysgc2FtcGxlcykKICAgIEFVVE9fVEhST1RUTEVEIC0tPiBPUFRJTUFMIDogYXZnIEZQUyA-IDE0IChzdXN0YWluZWQgcmVjb3ZlcnkpCgogICAgc3RhdGUgT1BUSU1BTCB7CiAgICAgICAgWypdIDogc2tpcEZyYW1lcyA9IDAKICAgICAgICBbKl0gOiBBbGwgZnJhbWVzIHByb2Nlc3NlZAogICAgICAgIFsqXSA6IEJhZGdlIE9QVElNQUwKICAgIH0KCiAgICBzdGF0ZSBBVVRPX1RIUk9UVExFRCB7CiAgICAgICAgWypdIDogc2tpcEZyYW1lcyA9IDEKICAgICAgICBbKl0gOiBFdmVyeSBvdGhlciBmcmFtZSBza2lwcGVkCiAgICAgICAgWypdIDogQmFkZ2UgVEhST1RUTEVECiAgICB9?type=png&bgColor=!white" alt="diagram" width="700">
</p>

<details>
<summary>Diagram source (Mermaid)</summary>

```mermaid
stateDiagram-v2
    [*] --> OPTIMAL
    OPTIMAL --> AUTO_THROTTLED : avg FPS < 8 (over 3+ samples)
    AUTO_THROTTLED --> OPTIMAL : avg FPS > 14 (sustained recovery)

    state OPTIMAL {
        [*] : skipFrames = 0
        [*] : All frames processed
        [*] : Badge OPTIMAL
    }

    state AUTO_THROTTLED {
        [*] : skipFrames = 1
        [*] : Every other frame skipped
        [*] : Badge THROTTLED
    }
```

</details>

<br/>

| Parameter            | Value       |
|:---------------------|:------------|
| `lowFpsThreshold`    | 8 FPS       |
| `highFpsThreshold`   | 14 FPS      |
| `fpsWindowSize`      | 5 samples   |
| `checkInterval`      | 2000ms      |
| Min samples needed   | 3           |

<br/>

</details>

<br/>

<details>
<summary><strong>5. Face Tracking Lifecycle</strong></summary>

<br/>

Each detected face gets a persistent monotonic ID (never recycled) and a unique
color from a 4-color palette (blue, orange, green, purple).

<br/>

<p align="center">
  <img src="https://mermaid.ink/img/Z3JhcGggVEQKICAgIEFbIk5ldyBmYWNlIGRldGVjdGVkIGluIGZyYW1lIl0gLS0-IEJbIm1hdGNoRmFjZXMoKSBkaXN0YW5jZSBjaGVjazxici8-Q29tcGFyZSBjZW50cm9pZCB0byBhbGwga25vd24gZmFjZXMiXQogICAgQiAtLT58Ik1BVENIRUQ8YnIvPihkaXN0IDwgdGhyZXNob2xkKSJ8IENbIlVwZGF0ZSBleGlzdGluZzxici8-bmV3IGNlbnRyb2lkLCByZXNldCBUVEwsPGJyLz51cGRhdGUgYm91bmRpbmcgYm94Il0KICAgIEIgLS0-fFVOTUFUQ0hFRHwgRFsiQXNzaWduIG5ldyBJRDxici8-bmV4dEZhY2VJZCsrLCBwaWNrIGNvbG9yLDxici8-cmVjb3JkIGJpcnRoIHRpbWUiXQogICAgQyAtLT4gRVsiVFJBQ0tFRCAoYWN0aXZlKTxici8-TGFiZWw6IEZhY2UgTiAtIDEyczxici8-VW5pcXVlIGNvbG9yIG92ZXJsYXk8YnIvPkJsaW5rL3B1cGlsL2V4cHJlc3Npb24iXQogICAgRCAtLT4gRQogICAgRSAtLT58ImZhY2UgZGlzYXBwZWFyczxici8-ZnJvbSBkZXRlY3Rpb24ifCBGWyJNSVNTSU5HIChUVEwgY291bnRkb3duKTxici8-ODAwbXMgZ3JhY2UgcGVyaW9kIl0KICAgIEYgLS0-fCJSZWFwcGVhcnMgPCA4MDBtcyJ8IEdbIlJFQ09WRVJFRDxici8-UmVzdW1lIHRyYWNrLCBzYW1lIElEL2NvbG9yIl0KICAgIEYgLS0-fCJUVEwgZXhwaXJlcyA-IDgwMG1zInwgSFsiRVhQSVJFRDxici8-UmVtb3ZlIGZyb20gdHJhY2tlZCBsaXN0PGJyLz5JRCByZXRpcmVkIl0KICAgIEcgLS0-IEU=?type=png&bgColor=!white" alt="diagram" width="700">
</p>

<details>
<summary>Diagram source (Mermaid)</summary>

```mermaid
graph TD
    A["New face detected in frame"] --> B["matchFaces() distance check<br/>Compare centroid to all known faces"]
    B -->|"MATCHED<br/>(dist < threshold)"| C["Update existing<br/>new centroid, reset TTL,<br/>update bounding box"]
    B -->|UNMATCHED| D["Assign new ID<br/>nextFaceId++, pick color,<br/>record birth time"]
    C --> E["TRACKED (active)<br/>Label: Face N - 12s<br/>Unique color overlay<br/>Blink/pupil/expression"]
    D --> E
    E -->|"face disappears<br/>from detection"| F["MISSING (TTL countdown)<br/>800ms grace period"]
    F -->|"Reappears < 800ms"| G["RECOVERED<br/>Resume track, same ID/color"]
    F -->|"TTL expires > 800ms"| H["EXPIRED<br/>Remove from tracked list<br/>ID retired"]
    G --> E
```

</details>

<br/>

> Distance matching uses a threshold that scales with face width, sorted by
> global minimum distance, with greedy assignment (closest pair first).
> Max tracked faces: 4 (`MAX_FACES`).

<br/>

</details>

<br/>

### 6. Bridge Communication Flow

Three layers communicate via two protocols: **WebSocket** (browser to MPU,
injected by the Brick SDK at runtime) and **Bridge RPC** (MPU to MCU).

<br/>

> **Important:** In the Replit preview, the browser runs standalone without the SDK,
> so face detection and rendering work but no data reaches the MPU or MCU.

<br/>

<p align="center">
  <img src="https://mermaid.ink/img/Z3JhcGggVEQKICAgIHN1YmdyYXBoIEJyb3dzZXJbIkJyb3dzZXIgKHZpYSBXZWJVSSBCcmljayBTREspIl0KICAgICAgICBCMVsiTWVkaWFQaXBlIGZhY2UgZGF0YSJdCiAgICAgICAgQjJbIlJHQiBidXR0b24gY2xpY2tzIl0KICAgICAgICBCM1siR1BJTyB0b2dnbGUgY2xpY2tzIl0KICAgICAgICBCNFsiQ2FwdHVyZSBzbmFwc2hvdCJdCiAgICBlbmQKCiAgICBzdWJncmFwaCBNUFVfTGF5ZXJbIk1QVSAoUHl0aG9uKSJdCiAgICAgICAgTTFbIm9uX2ZhY2VfZGF0YSgpPGJyLz5VcGRhdGUgc3RhdGUsIGRldGVybWluZSBleHByZXNzaW9uLDxici8-Y2FsbCBzaG93X2ZhY2Uvc2hvd19ub19mYWNlL3Nob3dfZXhwcmVzc2lvbiJdCiAgICAgICAgTTJbIm9uX3JnYl9jb250cm9sKCk8YnIvPmNhbGwgc2V0X3JnYiJdCiAgICAgICAgTTNbIm9uX2dwaW9fY29udHJvbCgpPGJyLz5jYWxsIHNldF9ncGlvIl0KICAgICAgICBNNFsic2FmZV9icmlkZ2VfY2FsbChtZXRob2QsIGFyZ3MpPGJyLz50cnkvZXhjZXB0LCBuZXZlciBjcmFzaCJdCiAgICBlbmQKCiAgICBzdWJncmFwaCBNQ1VfTGF5ZXJbIk1DVSAoU1RNMzJVNTg1KSAtLSAxMCBCcmlkZ2UgcHJvdmlkZXJzIl0KICAgICAgICBDMVsic2Nyb2xsX3RleHQsIHNob3dfZmFjZSwgc2hvd19ub19mYWNlIl0KICAgICAgICBDMlsiZmxhc2hfZmFjZSwgc2hvd19leHByZXNzaW9uIl0KICAgICAgICBDM1sic2V0X2RldmljZV9tb2RlLCBzZXRfcmdiIl0KICAgICAgICBDNFsic2V0X2dwaW8sIHJlcG9ydF9zdGF0dXMsIG1wdV9hY2siXQogICAgZW5kCgogICAgQnJvd3NlciAtLT58IldlYlNvY2tldCAoSlNPTikifCBNUFVfTGF5ZXIKICAgIE1QVV9MYXllciAtLT58IkJyaWRnZSBSUEMifCBNQ1VfTGF5ZXIKICAgIE1DVV9MYXllciAtLT58IkJyaWRnZS5jYWxsIG1jdV9yZWFkeSJ8IE1QVV9MYXllcg==?type=png&bgColor=!white" alt="diagram" width="700">
</p>

<details>
<summary>Diagram source (Mermaid)</summary>

```mermaid
graph TD
    subgraph Browser["Browser (via WebUI Brick SDK)"]
        B1["MediaPipe face data"]
        B2["RGB button clicks"]
        B3["GPIO toggle clicks"]
        B4["Capture snapshot"]
    end

    subgraph MPU_Layer["MPU (Python)"]
        M1["on_face_data()<br/>Update state, determine expression,<br/>call show_face/show_no_face/show_expression"]
        M2["on_rgb_control()<br/>call set_rgb"]
        M3["on_gpio_control()<br/>call set_gpio"]
        M4["safe_bridge_call(method, args)<br/>try/except, never crash"]
    end

    subgraph MCU_Layer["MCU (STM32U585) -- 10 Bridge providers"]
        C1["scroll_text, show_face, show_no_face"]
        C2["flash_face, show_expression"]
        C3["set_device_mode, set_rgb"]
        C4["set_gpio, report_status, mpu_ack"]
    end

    Browser -->|"WebSocket (JSON)"| MPU_Layer
    MPU_Layer -->|"Bridge RPC"| MCU_Layer
    MCU_Layer -->|"Bridge.call mcu_ready"| MPU_Layer
```

</details>

<br/>

#### MCU Bridge Providers

| Provider                  | Action                                                    |
|:--------------------------|:----------------------------------------------------------|
| **`scroll_text(text)`**   | Display `frame_smiley` (no text scroll on Zephyr)         |
| **`show_face()`**         | Smiley bitmap + green RGB + relay ON                      |
| **`show_no_face()`**      | X bitmap + red RGB + relay OFF                            |
| **`flash_face(count)`**   | Rapid flash N times + buzzer beep                         |
| **`show_expression(e)`**  | Expression bitmap + color-coded RGB                       |
| **`set_device_mode(m)`**  | Store mode string (no hardware change)                    |
| **`set_rgb(color)`**      | Set RGB LED (8 colors + off)                              |
| **`set_gpio(pin:state)`** | Toggle pin if in allowlist and enabled                    |
| **`report_status()`**     | Send uptime/faces/mode to MPU                             |
| **`mpu_ack()`**           | Acknowledge MPU handshake, stop retry loop                |

<br/>

<details>
<summary><strong>7. RGB LED State Machine</strong></summary>

<br/>

LED4 is active-low (`LOW` = ON, `HIGH` = OFF).
Supported colors: red, green, blue, yellow, cyan, magenta, white, off.

<br/>

<p align="center">
  <img src="https://mermaid.ink/img/c3RhdGVEaWFncmFtLXYyCiAgICBbKl0gLS0-IE9GRgogICAgT0ZGIC0tPiBTRUxGX1RFU1QgOiBCb290CiAgICBTRUxGX1RFU1QgLS0-IFJFRF9JRExFIDogU2VsZi10ZXN0IGNvbXBsZXRlCgogICAgc3RhdGUgU0VMRl9URVNUIHsKICAgICAgICBbKl0gOiBSIHRoZW4gRyB0aGVuIEIgKDMwMG1zIGVhY2gpCiAgICB9CgogICAgc3RhdGUgUkVEX0lETEUgewogICAgICAgIFsqXSA6IFdhaXRpbmcgZm9yIGZhY2UKICAgIH0KCiAgICBSRURfSURMRSAtLT4gR1JFRU5fVFJBQ0tJTkcgOiBGYWNlIGRldGVjdGVkCiAgICBSRURfSURMRSAtLT4gUkVEX0lETEUgOiBObyBjaGFuZ2UKCiAgICBzdGF0ZSBHUkVFTl9UUkFDS0lORyB7CiAgICAgICAgWypdIDogRmFjZSBwcmVzZW50CiAgICB9CgogICAgR1JFRU5fVFJBQ0tJTkcgLS0-IEdSRUVOX1NNSUxFIDogRXhwcmVzc2lvbiA9IHNtaWxlCiAgICBHUkVFTl9UUkFDS0lORyAtLT4gQkxVRV9TVVJQUklTRSA6IEV4cHJlc3Npb24gPSBzdXJwcmlzZQogICAgR1JFRU5fVFJBQ0tJTkcgLS0-IFlFTExPV19FWUVCUk9XIDogRXhwcmVzc2lvbiA9IGV5ZWJyb3cgcmFpc2UKICAgIEdSRUVOX1RSQUNLSU5HIC0tPiBSRURfSURMRSA6IEZhY2UgbG9zdA==?type=png&bgColor=!white" alt="diagram" width="700">
</p>

<details>
<summary>Diagram source (Mermaid)</summary>

```mermaid
stateDiagram-v2
    [*] --> OFF
    OFF --> SELF_TEST : Boot
    SELF_TEST --> RED_IDLE : Self-test complete

    state SELF_TEST {
        [*] : R then G then B (300ms each)
    }

    state RED_IDLE {
        [*] : Waiting for face
    }

    RED_IDLE --> GREEN_TRACKING : Face detected
    RED_IDLE --> RED_IDLE : No change

    state GREEN_TRACKING {
        [*] : Face present
    }

    GREEN_TRACKING --> GREEN_SMILE : Expression = smile
    GREEN_TRACKING --> BLUE_SURPRISE : Expression = surprise
    GREEN_TRACKING --> YELLOW_EYEBROW : Expression = eyebrow raise
    GREEN_TRACKING --> RED_IDLE : Face lost
```

</details>

<br/>

</details>

<br/>

<details>
<summary><strong>8. Overlay Rendering Order</strong></summary>

<br/>

Each frame draws layers in a specific order. The overlay preset controls
which layers are visible.

<br/>

| Layer  | Content                           | Visibility                   |
|:-------|:----------------------------------|:-----------------------------|
| 0      | Video frame (via cam element)     | Always                       |
| 1      | Face mesh tessellation            | Toggleable                   |
| 2      | Face contour / jawline            | Toggleable                   |
| 3      | Eye outline connections           | Toggleable                   |
| 4      | Eyebrow connections               | Toggleable                   |
| 5      | Lip connections                   | Toggleable                   |
| 6      | Face oval (outer contour)         | Toggleable                   |
| 7      | Iris connections + pupil ring     | Toggleable                   |
| 8      | Iris diameter measurement         | Always (when iris visible)   |
| 9      | Landmark dots (478 per face)      | Toggleable                   |
| 10     | Emoji expression indicators       | Toggleable                   |
| 11     | Blink flash (hot pink)            | Triggered on blink           |
| 12     | Face label ("Face N -- 12s")      | Always                       |
| 13     | System stats overlay              | Always (top-right)           |
| 14     | HUD ticker                        | Always (bottom-center)       |

<br/>

**Overlay Presets:**

| Preset                  | Mesh | Outline | Eyes | Brows | Lips | Iris | Dots | Emoji |
|:------------------------|:----:|:-------:|:----:|:-----:|:----:|:----:|:----:|:-----:|
| **Full Mesh+Features**  |  Y   |    Y    |  Y   |   Y   |  Y   |  Y   |  Y   |   Y   |
| **Outline+Features**    |  -   |    Y    |  Y   |   Y   |  Y   |  Y   |  -   |   Y   |
| **Mesh Only**           |  Y   |    -    |  -   |   -   |  -   |  -   |  -   |   -   |
| **Dots Only**           |  -   |    -    |  -   |   -   |  -   |  -   |  Y   |   -   |
| **Minimal**             |  -   |    Y    |  -   |   -   |  -   |  Y   |  -   |   -   |
| **Outline+Emojis**      |  -   |    Y    |  -   |   -   |  Y   |  -   |  -   |   Y   |

<br/>

</details>

<br/>

<details>
<summary><strong>9. Delegate Selection and Validation Flow</strong></summary>

<br/>

The QRB2210's Adreno 702 GPU supports WebGL, but MediaPipe's GPU delegate
produces spatially incorrect landmarks. The app uses CPU-first with automatic
runtime validation.

<br/>

<p align="center">
  <img src="https://mermaid.ink/img/Z3JhcGggVEQKICAgIEFbIkFwcCBTdGFydCJdIC0tPiBCWyJUcnkgQ1BVIGRlbGVnYXRlIChXQVNNKSJdCiAgICBCIC0tPnxTVUNDRVNTfCBDWyJDUFUgbG9hZGVkIl0KICAgIEIgLS0-fEZBSUx8IERbIlRyeSBHUFUgZGVsZWdhdGUgKFdlYkdML0FkcmVubykiXQogICAgRCAtLT58U1VDQ0VTU3wgRVsiR1BVIGxvYWRlZCJdCiAgICBEIC0tPnxGQUlMfCBGWyJGQVRBTCAtIG5vIGRlbGVnYXRlIl0KICAgIEMgLS0-IEdbIlVOVEVTVEVEPGJyLz5XYWl0aW5nIGZvciBmaXJzdCBmYWNlLi4uIl0KICAgIEUgLS0-IEcKICAgIEcgLS0-fCJGaXJzdCBmYWNlIGRldGVjdGVkInwgSFsiVkFMSURBVElORzxici8-NiBzYW5pdHkgY2hlY2tzIHggNSBmcmFtZXMiXQogICAgSCAtLT58IjMrIFBBU1MifCBJWyJQQVNTRUQiXQogICAgSCAtLT58IjMrIEZBSUwifCBKWyJGQUlMRUQ8YnIvPmF1dG8tc3dpdGNoIGRlbGVnYXRlLCByZWxvYWQgbW9kZWwiXQogICAgSSAtLT58IkV2ZXJ5IDYwcyJ8IEtbIlJlLXZhbGlkYXRlIDUgZnJhbWVzIl0KICAgIEsgLS0-fERlZ3JhZGVkfCBMWyJXYXJuIChubyBhdXRvLXN3aXRjaCkiXQogICAgSyAtLT58T0t8IEk=?type=png&bgColor=!white" alt="diagram" width="700">
</p>

<details>
<summary>Diagram source (Mermaid)</summary>

```mermaid
graph TD
    A["App Start"] --> B["Try CPU delegate (WASM)"]
    B -->|SUCCESS| C["CPU loaded"]
    B -->|FAIL| D["Try GPU delegate (WebGL/Adreno)"]
    D -->|SUCCESS| E["GPU loaded"]
    D -->|FAIL| F["FATAL - no delegate"]
    C --> G["UNTESTED<br/>Waiting for first face..."]
    E --> G
    G -->|"First face detected"| H["VALIDATING<br/>6 sanity checks x 5 frames"]
    H -->|"3+ PASS"| I["PASSED"]
    H -->|"3+ FAIL"| J["FAILED<br/>auto-switch delegate, reload model"]
    I -->|"Every 60s"| K["Re-validate 5 frames"]
    K -->|Degraded| L["Warn (no auto-switch)"]
    K -->|OK| I
```

</details>

<br/>

**Sanity checks per frame:**

| Check  | Condition                    |
|:-------|:-----------------------------|
| 1      | Landmark count = 478         |
| 2      | Bounding box > 3% of frame   |
| 3      | Out-of-bounds points < 20    |
| 4      | Nose near face center        |
| 5      | Eye separation 2-50%         |
| 6      | Forehead above chin          |

<br/>

</details>

<br/>

<details>
<summary><strong>10. WebSocket Telemetry Flow</strong></summary>

<br/>

Face data flows from the browser to the MPU, which drives MCU hardware responses.

<br/>

<p align="center">
  <img src="https://mermaid.ink/img/c2VxdWVuY2VEaWFncmFtCiAgICBwYXJ0aWNpcGFudCBCcm93c2VyCiAgICBwYXJ0aWNpcGFudCBNUFUgYXMgTVBVIChtYWluLnB5KQogICAgcGFydGljaXBhbnQgTUNVIGFzIE1DVSAoc2tldGNoLmlubykKCiAgICBOb3RlIG92ZXIgQnJvd3NlcjogRXZlcnkgNTAwbXMgd2hlbiBmYWNlcyBwcmVzZW50CiAgICBCcm93c2VyLT4-TVBVOiBlbWl0KCJmYWNlX2RhdGEiLCB7ZmFjZXMsIGJsaW5rcywgZXhwcmVzc2lvbiwgcHVwaWxzLCB5YXcsIHBpdGNofSkKICAgIE1QVS0-Pk1QVTogUGFyc2UgSlNPTiwgdXBkYXRlIGZhY2Vfc3RhdGUKCiAgICBhbHQgTm8gZmFjZSAtPiBGYWNlIGFwcGVhcmVkCiAgICAgICAgTVBVLT4-TUNVOiBmbGFzaF9mYWNlKDMpCiAgICAgICAgTVBVLT4-TUNVOiBzaG93X2ZhY2UoKQogICAgICAgIE5vdGUgb3ZlciBNQ1U6IEdyZWVuIFJHQgogICAgZWxzZSBFeHByZXNzaW9uIGNoYW5nZWQKICAgICAgICBNUFUtPj5NQ1U6IHNob3dfZXhwcmVzc2lvbihleHByKQogICAgICAgIE5vdGUgb3ZlciBNQ1U6IENvbG9yLWNvZGVkIFJHQgogICAgZWxzZSBGYWNlIC0-IE5vIGZhY2UKICAgICAgICBNUFUtPj5NQ1U6IHNob3dfbm9fZmFjZSgpCiAgICAgICAgTm90ZSBvdmVyIE1DVTogUmVkIFJHQgogICAgZW5kCgogICAgTVBVLT4-QnJvd3NlcjogZW1pdCgic3RhdGVfdXBkYXRlIiwgZnVsbF9zdGF0ZV9qc29uKQ==?type=png&bgColor=!white" alt="diagram" width="700">
</p>

<details>
<summary>Diagram source (Mermaid)</summary>

```mermaid
sequenceDiagram
    participant Browser
    participant MPU as MPU (main.py)
    participant MCU as MCU (sketch.ino)

    Note over Browser: Every 500ms when faces present
    Browser->>MPU: emit("face_data", {faces, blinks, expression, pupils, yaw, pitch})
    MPU->>MPU: Parse JSON, update face_state

    alt No face -> Face appeared
        MPU->>MCU: flash_face(3)
        MPU->>MCU: show_face()
        Note over MCU: Green RGB
    else Expression changed
        MPU->>MCU: show_expression(expr)
        Note over MCU: Color-coded RGB
    else Face -> No face
        MPU->>MCU: show_no_face()
        Note over MCU: Red RGB
    end

    MPU->>Browser: emit("state_update", full_state_json)
```

</details>

<br/>

</details>

<br/>

---

<br/>

## Performance

| Stage                                     | Typical Latency   | Bottleneck                  |
|:------------------------------------------|:------------------|:----------------------------|
| USB camera capture                        | ~67ms (15 FPS)    | UVC webcam frame rate       |
| MediaPipe WASM inference                  | ~5-15ms           | CPU (4x A53 cores)          |
| Canvas rendering (per face)               | ~1-2ms            | GPU compositing             |
| WebSocket emit (throttled)                | 500ms interval    | Intentional throttle        |
| Bridge RPC (MPU to MCU)                   | ~2-5ms            | Serial transport            |
| LED matrix update                         | <1ms              | SPI to matrix driver        |
| **Browser-side (camera to overlay)**      | **~75-90ms**      | **Camera is the ceiling**   |
| **Full loop (camera to LED)**             | **~500-575ms**    | **WebSocket throttle**      |

<br/>

> **Key insight:** Browser-side rendering runs at full frame rate -- the camera
> is the ceiling. The MCU hardware response is gated by the 500ms WebSocket
> throttle, making end-to-end latency ~500-575ms. This throttle is intentional
> to avoid flooding the Bridge RPC channel.

<br/>

The camera is the dominant bottleneck. The QRB2210's dual ISPs support up to
25 MP at 30 FPS through MIPI-CSI, but this demo uses a USB webcam at 640x480 / 15 FPS.
The [UNO Media Carrier](https://docs.arduino.cc/hardware/uno-media-carrier/) with a
MIPI-CSI camera would roughly double the frame rate.

<br/>

---

<br/>

## GPIO Placeholders

Pre-configured pins for extending the demo. All set as `OUTPUT` at boot but
remain `LOW` unless their enable flag is set to `true` in `sketch.ino`. The
MCU enforces a pin allowlist -- only D3-D7 can be toggled, and only when enabled.

<br/>

| Pin     | Name           | Default    | Use Case                                       |
|:--------|:---------------|:-----------|:-----------------------------------------------|
| **D7**  | `PIN_RELAY`    | disabled   | Modulino Relay or generic 5V relay             |
| **D6**  | `PIN_EXT_LED`  | disabled   | WS2812B NeoPixel strip data pin                |
| **D5**  | `PIN_BUZZER`   | disabled   | Piezo buzzer (beep on face detection)          |
| **D4**  | `PIN_AUX_1`    | disabled   | General-purpose (servo, sensor, Modulino)      |
| **D3**  | `PIN_AUX_2`    | disabled   | General-purpose (PWM capable)                  |

<br/>

> **How to use:**
>
> - **Enable in firmware:** Set `enableRelay = true` (etc.) in `sketch.ino`
> - **Control from Python:** `Bridge.call("set_gpio", "7:1")`
> - **Control from browser (App Lab only):** WebSocket `gpio_control` event with `{pin: 7, state: 1}`

<br/>

---

<br/>

## WebSocket Events

| Event                | Direction         | Payload                                                          |
|:---------------------|:------------------|:-----------------------------------------------------------------|
| **`face_data`**      | Browser -> MPU    | `{faces, blinks, expression, pupilL, pupilR, yaw, pitch}`       |
| **`capture_snapshot`** | Browser -> MPU  | Snapshot request                                                 |
| **`rgb_control`**    | Browser -> MPU    | `{"color": "green"}` (App Lab WebSocket only)                    |
| **`gpio_control`**   | Browser -> MPU    | `{"pin": 7, "state": 1}` (App Lab WebSocket only)               |
| **`state_update`**   | MPU -> Browser    | Full face state JSON                                             |
| **`snapshot_ack`**   | MPU -> Browser    | `{"status": "ok", "timestamp": "..."}`                           |
| **`mpu_face_data`**  | MPU -> Browser    | `{faces, source:"mpu", inference_ms, detections}` (AI Hub)      |
| **`ai_status`**      | MPU -> Browser    | `{available, status, model, running, fps, inference_ms}`         |
| **`ai_toggle`**      | Browser -> MPU    | `{enable: true/false}` (start/stop on-device detection)          |

<br/>

---

<br/>

## Dependencies

Designed to pull as few external resources as possible.

<br/>

### MCU (`sketch.ino`)

| Library                    | Version      | Notes                                         |
|:---------------------------|:-------------|:----------------------------------------------|
| **Arduino_RouterBridge**   | 0.4.1        | Bridge RPC (primary dep in `sketch.yaml`)     |
| Arduino_RPClite            | 0.2.1        | Transitive dep of RouterBridge                |
| ArxContainer               | 0.7.0        | Transitive dep of RouterBridge                |
| ArxTypeTraits              | 0.3.2        | Transitive dep of RouterBridge                |
| DebugLog                   | 0.8.4        | Transitive dep of RouterBridge                |
| MsgPack                    | 0.4.2        | Transitive dep of RouterBridge                |
| **Arduino_LED_Matrix**     | (platform)   | Bundled with `arduino:zephyr` board core      |

<br/>

### MPU (`python/main.py`)

App Lab SDK (`arduino.app_utils`, `arduino.app_bricks.web_ui`) + Python stdlib.

**Optional** for on-device AI: `tflite-runtime`, `numpy`, `opencv-python-headless`.

For model compilation on a dev machine (not the Uno Q): `qai-hub`, `qai_hub_models`, `torch`.

<br/>

### Browser (`assets/index.html`)

| Resource                                  | CDN                    | Pinned       | Required                              |
|:------------------------------------------|:-----------------------|:-------------|:--------------------------------------|
| **@mediapipe/tasks-vision**               | jsdelivr               | 0.10.3       | Yes                                   |
| **face_landmarker.task model**            | Google Cloud Storage   | float16/1    | Yes (~4MB, cached after first load)   |
| Google Fonts (Inter, JetBrains Mono)      | Google Fonts           | latest       | No (degrades to system fonts)         |

<br/>

---

<br/>

## Advanced Topics

<details>
<summary><strong>Beyond Face Tracking: Industrial and Pro Applications</strong></summary>

<br/>

This demo is a proof-of-concept, but the pattern it demonstrates -- AI inference
feeding into a Python coordinator on Debian, which drives real-time MCU actuation
via Bridge RPC -- applies directly to [Arduino Pro](https://www.arduino.cc/pro/)
industrial use cases.

<br/>

| Application                  | How It Works With This Architecture                                                                                  |
|:-----------------------------|:---------------------------------------------------------------------------------------------------------------------|
| **Access control**           | Replace LED feedback with a relay on D7 for a door strike. `show_face()` = relay HIGH, `show_no_face()` = relay OFF  |
| **Occupancy monitoring**     | Use persistent face count (`MAX_FACES = 4`) and tracking lifecycle. Forward count to BMS via Wi-Fi                   |
| **Safety compliance**        | Swap MediaPipe for `arduino:object_detection` Brick (YOLOX-Nano). Detect PPE/hard hats. Buzzer on D5 for alerts     |
| **Quality inspection**       | Mount MIPI-CSI camera via Media Carrier. Vision model + Python classification + MCU GPIO for reject actuators        |
| **Operator presence**        | Face tracking 800ms TTL as presence signal. Wire D7 to safety interlock relay. MCU at Zephyr real-time priority      |
| **Retail analytics**         | Count foot traffic, measure dwell time via persistent face IDs. Forward to Arduino Cloud dashboards                  |
| **Agriculture**              | Replace camera AI with sensor Bricks (Modulino Movement, Distance). MCU drives pumps, valves, alerts via GPIO       |

<br/>

</details>

<br/>

<details>
<summary><strong>The App Lab and Bricks Experience</strong></summary>

<br/>

The [Arduino App Lab](https://docs.arduino.cc/software/app-lab/) is a unified development
environment that lets you combine Arduino sketches, Python scripts, and containerized
Linux applications into a single workflow.

<br/>

<p align="center">
  <img src="https://docs.arduino.cc/static/782ed8393ae066932b79a19418651a50/a6d36/app-lab.png" alt="Arduino App Lab" width="600">
</p>

<br/>

[Bricks](https://docs.arduino.cc/software/app-lab/tutorials/bricks) are code building
blocks that abstract away complexity. This project uses a single Brick:

- **`arduino:web_ui`** -- serves the contents of `assets/` as a web application and
  provides WebSocket messaging between the browser and `python/main.py`. The Brick
  injects WebSocket connectivity at runtime. No explicit socket code is needed in the HTML.

<br/>

<p align="center">
  <img src="https://docs.arduino.cc/static/c4ba129c26c39fd5f37d2dfed7fee780/a6d36/add-brick-1.png" alt="Adding a Brick in App Lab" width="500">
</p>

<br/>

> **Tip:** To install this demo, download the repository as a `.zip`, open
> [Arduino App Lab](https://www.arduino.cc/en/software/#app-lab-section),
> click **Import App**, and select the file.

<br/>

</details>

<br/>

<details>
<summary><strong>Expanding the Hardware</strong></summary>

<br/>

The Uno Q retains the classic UNO form factor for shield compatibility, and adds
two bottom-mounted high-speed connectors (JMEDIA and JMISC) for advanced peripherals.

<br/>

<p align="center">
  <img src="https://docs.arduino.cc/static/7d5a122fd16435d60983ecb96c2e490f/a6d36/uno-form-factor.png" alt="UNO form factor" width="500">
</p>

<br/>

**Carrier boards:**

| Carrier                                                                             | What It Adds                                                                                          |
|:------------------------------------------------------------------------------------|:------------------------------------------------------------------------------------------------------|
| [**UNO Media Carrier**](https://docs.arduino.cc/hardware/uno-media-carrier/)        | Dual MIPI-CSI camera connectors (RPi compatible), MIPI-DSI display output, three 3.5 mm audio jacks  |
| [**UNO Breakout Carrier**](https://docs.arduino.cc/hardware/uno-breakout-carrier/)  | Full breakout of JMEDIA/JMISC signals to 2.54 mm headers -- audio, I2C, SPI, UART, PWM, PSSI, GPIO   |

<br/>

**Qwiic / Modulino sensors** (no soldering, I2C on Wire1):

| Modulino                                                                              | Use With This Demo                                                           |
|:--------------------------------------------------------------------------------------|:-----------------------------------------------------------------------------|
| [**Modulino Movement**](https://docs.arduino.cc/hardware/modulino-movement/)          | LSM6DSOX accelerometer/gyroscope -- detect tilt/movement while tracking      |
| [**Modulino Distance**](https://docs.arduino.cc/hardware/modulino-distance/)          | Time-of-flight -- measure viewer distance from camera                        |
| [**Modulino Buttons**](https://docs.arduino.cc/hardware/modulino-buttons/)            | Physical buttons -- cycle overlay presets or toggle tracking                  |

<br/>

</details>

<br/>

<details>
<summary><strong>Arduino Cloud Integration (Future)</strong></summary>

<br/>

The current demo runs entirely on the local network.
[Arduino Cloud](https://docs.arduino.cc/arduino-cloud/) could add:

- Log timestamp and screenshot of each new face detection to a cloud Thing
- Persistent face count across sessions (daily/weekly)
- Live dashboard showing tracking state, uptime, and system health remotely
- Webhook notifications when a face is detected (or absent for a threshold period)
- Historical data export via [Arduino Cloud's built-in data export](https://docs.arduino.cc/arduino-cloud/features/iot-cloud-historical-data/)

<br/>

> The Uno Q's built-in Wi-Fi and the WebUI Brick's `web_ui.expose_api()` pattern
> make this feasible without restructuring the app.

<br/>

</details>

<br/>

<details>
<summary><strong>Advanced AI Model Options</strong></summary>

<br/>

> **Warning:** The sections below describe AI model workflows that are technically
> possible on the Uno Q's QRB2210 but are **not part of this demo** and **not included
> in the App Lab zip**. They require additional software (`tflite-runtime`, OpenCV,
> numpy), a camera on the MPU, and in some cases cloud accounts.

<br/>

#### What is Qualcomm AI Hub?

[Qualcomm AI Hub](https://aihub.qualcomm.com/) takes pre-trained AI models (PyTorch,
ONNX, TensorFlow) and compiles them into optimized runtimes for specific Qualcomm chipsets.

<br/>

<p align="center">
  <img src="https://mermaid.ink/img/Z3JhcGggTFIKICAgIHN1YmdyYXBoIElucHV0WyJZb3VyIE1vZGVsIl0KICAgICAgICBBWyJQeVRvcmNoIC8gT05OWCAvPGJyLz5URi1LZXJhcyAvIEpBWCJdCiAgICBlbmQKCiAgICBzdWJncmFwaCBDbG91ZFsiQUkgSHViIENsb3VkIl0KICAgICAgICBCWyIxLiBPUFRJTUlaRTxici8-UXVhbnRpemUgSU5UOCwgZnVzZSBvcHMiXQogICAgICAgIENbIjIuIENPTVBJTEU8YnIvPlRhcmdldDogUVJCMjIxMDxici8-UnVudGltZTogVEZMaXRlIG9yIFFOTiJdCiAgICAgICAgRFsiMy4gUFJPRklMRTxici8-TGF0ZW5jeSwgRlBTLCBtZW1vcnksPGJyLz5sYXllci1ieS1sYXllciJdCiAgICAgICAgQiAtLT4gQyAtLT4gRAogICAgZW5kCgogICAgc3ViZ3JhcGggRGV2aWNlWyJUYXJnZXQgRGV2aWNlIl0KICAgICAgICBFWyJVbm8gUSAoUVJCMjIxMCk8YnIvPm9yIGFueSBTbmFwZHJhZ29uIl0KICAgIGVuZAoKICAgIEEgLS0-fHVwbG9hZHwgQgogICAgRCAtLT58ImRvd25sb2FkIC50ZmxpdGUgLyAuZGxjInwgRQ==?type=png&bgColor=!white" alt="diagram" width="700">
</p>

<details>
<summary>Diagram source (Mermaid)</summary>

```mermaid
graph LR
    subgraph Input["Your Model"]
        A["PyTorch / ONNX /<br/>TF-Keras / JAX"]
    end

    subgraph Cloud["AI Hub Cloud"]
        B["1. OPTIMIZE<br/>Quantize INT8, fuse ops"]
        C["2. COMPILE<br/>Target: QRB2210<br/>Runtime: TFLite or QNN"]
        D["3. PROFILE<br/>Latency, FPS, memory,<br/>layer-by-layer"]
        B --> C --> D
    end

    subgraph Device["Target Device"]
        E["Uno Q (QRB2210)<br/>or any Snapdragon"]
    end

    A -->|upload| B
    D -->|"download .tflite / .dlc"| E
```

</details>

<br/>

#### On-Device Inference via AI Hub

The `python/face_detector_mpu.py` module implements an alternative path: face detection
runs natively on the QRB2210 using `tflite-runtime`, bypassing the browser.

<br/>

<p align="center">
  <img src="https://mermaid.ink/img/Z3JhcGggTFIKICAgIEFbIkNhbWVyYSAodjRsMi9VU0IpIl0gLS0-IEJbIk9wZW5DViBjYXB0dXJlIl0KICAgIEIgLS0-IENbIlRGTGl0ZSBpbmZlcmVuY2UgKENQVSkiXQogICAgQyAtLT4gRFsiRmFjZSByZXN1bHRzIl0KICAgIEQgLS0-IEVbIkJyaWRnZSBSUEMgdG8gTUNVPGJyLz4oTEVEL1JHQikiXQogICAgRCAtLT4gRlsiV2ViU29ja2V0IHRvIEJyb3dzZXI8YnIvPihvdmVybGF5KSJd?type=png&bgColor=!white" alt="diagram" width="700">
</p>

<details>
<summary>Diagram source (Mermaid)</summary>

```mermaid
graph LR
    A["Camera (v4l2/USB)"] --> B["OpenCV capture"]
    B --> C["TFLite inference (CPU)"]
    C --> D["Face results"]
    D --> E["Bridge RPC to MCU<br/>(LED/RGB)"]
    D --> F["WebSocket to Browser<br/>(overlay)"]
```

</details>

<br/>

**TFLite delegates on QRB2210:**

<br/>

<p align="center">
  <img src="https://raw.githubusercontent.com/tensorflow/tensorflow/master/tensorflow/lite/g3doc/images/convert/workflow.svg" alt="TensorFlow Lite conversion and inference workflow" width="700">
</p>

<br/>

<p align="center">
  <img src="https://mermaid.ink/img/Z3JhcGggVEQKICAgIEFbIi50ZmxpdGUgbW9kZWwgZmlsZSJdIC0tPiBCWyJURkxpdGUgSW50ZXJwcmV0ZXI8YnIvPkxvYWQsIEFsbG9jYXRlLCBJbnZva2UiXQogICAgQiAtLT4gQ3siRGVsZWdhdGUgc2VsZWN0aW9uIn0KICAgIEMgLS0-IERbIlhOTlBBQ0sgKENQVSk8YnIvPkRFRkFVTFQgLSByZWxpYWJsZSJdCiAgICBDIC0tPiBFWyJHUFUgKEFkcmVubyA3MDIpPGJyLz5BdmFpbGFibGUgYnV0IHVucmVsaWFibGU8YnIvPmZvciBsYW5kbWFya3MiXQogICAgQyAtLT4gRlsiSGV4YWdvbiAoTlBVKTxici8-Ti9BIG9uIFFSQjIyMTAiXQ==?type=png&bgColor=!white" alt="diagram" width="700">
</p>

<details>
<summary>Diagram source (Mermaid)</summary>

```mermaid
graph TD
    A[".tflite model file"] --> B["TFLite Interpreter<br/>Load, Allocate, Invoke"]
    B --> C{"Delegate selection"}
    C --> D["XNNPACK (CPU)<br/>DEFAULT - reliable"]
    C --> E["GPU (Adreno 702)<br/>Available but unreliable<br/>for landmarks"]
    C --> F["Hexagon (NPU)<br/>N/A on QRB2210"]
```

</details>

<br/>

**Hardware constraints on the QRB2210:**

| Spec         | Value                                | Impact                                                         |
|:-------------|:-------------------------------------|:---------------------------------------------------------------|
| **CPU**      | Cortex-A53 @ 2.0 GHz (4 cores)      | TFLite runs here. INT8 face_det_lite: ~5-15ms/frame            |
| **GPU**      | Adreno 702 @ 845 MHz                | GPU delegate available but slower for small models             |
| **NPU/TPU**  | None (0 TOPS)                        | No hardware neural network accelerator                         |
| **Camera**   | USB (UVC) or MIPI-CSI via Carrier    | 640x480 @ 15 FPS ceiling for USB                               |
| **RAM**      | 2 GB or 4 GB LPDDR4                 | Model + OpenCV + TFLite uses ~80-120 MB                        |

<br/>

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

<br/>

> **Tip:** The system always works without AI Hub models. Missing dependencies
> result in graceful fallback to browser-only mode (MediaPipe WASM).

<br/>

**Inference Approaches Comparison:**

| Approach                         | In This Demo?  | Where It Runs          | Setup Effort                          | Best For                               |
|:---------------------------------|:--------------:|:-----------------------|:--------------------------------------|:---------------------------------------|
| **Browser (MediaPipe WASM)**     | **Yes**        | Client browser         | Zero -- loads from CDN                | Demos, face landmarks (this demo)      |
| **App Lab Brick**                | Partially      | QRB2210 Docker         | Low -- add one line to `app.yaml`     | Standard tasks (object detection)      |
| AI Hub TFLite                    | No             | QRB2210 MPU native     | Medium -- compile + install deps      | Optimized headless inference           |
| Hugging Face model               | No             | QRB2210 MPU native     | Medium-High -- export to TFLite       | Research models, niche tasks           |
| Custom model (Edge Impulse)      | No             | QRB2210 MPU native     | High -- train + export + deploy       | Domain-specific, proprietary data      |

<br/>

#### Bringing a Hugging Face Model

Models on [Hugging Face Hub](https://huggingface.co/) that can be exported to TFLite
format can run on the Uno Q using the same `tflite-runtime` infrastructure.

<br/>

<p align="center">
  <img src="https://mermaid.ink/img/Z3JhcGggTFIKICAgIHN1YmdyYXBoIEhGWyJIdWdnaW5nIEZhY2UgSHViIl0KICAgICAgICBBWyJQeVRvcmNoIC8gVEYtS2VyYXMgLzxici8-SkFYIC8gT05OWCBtb2RlbHMiXQogICAgZW5kCgogICAgc3ViZ3JhcGggQ29udmVydFsiQ29udmVyc2lvbiJdCiAgICAgICAgQlsiT3B0aW9uIEE6IG9wdGltdW0tY2xpPGJyLz5leHBvcnQgdGZsaXRlIC0tcXVhbnRpemUgaW50OCJdCiAgICAgICAgQ1siT3B0aW9uIEI6IEFJIEh1Yjxici8-Y29tcGlsZSBmb3IgUVJCMjIxMCJdCiAgICBlbmQKCiAgICBzdWJncmFwaCBVbm9RWyJVbm8gUSAoUVJCMjIxMCkiXQogICAgICAgIERbInB5dGhvbi9tb2RlbHMvPGJyLz5tb2RlbC50ZmxpdGU8YnIvPmF1dG8tZGlzY292ZXJlZCBhdCBib290Il0KICAgIGVuZAoKICAgIEEgLS0-fCJBInwgQiAtLT58c2NwfCBECiAgICBBIC0tPnwiQiJ8IEMgLS0-fHNjcHwgRA==?type=png&bgColor=!white" alt="diagram" width="700">
</p>

<details>
<summary>Diagram source (Mermaid)</summary>

```mermaid
graph LR
    subgraph HF["Hugging Face Hub"]
        A["PyTorch / TF-Keras /<br/>JAX / ONNX models"]
    end

    subgraph Convert["Conversion"]
        B["Option A: optimum-cli<br/>export tflite --quantize int8"]
        C["Option B: AI Hub<br/>compile for QRB2210"]
    end

    subgraph UnoQ["Uno Q (QRB2210)"]
        D["python/models/<br/>model.tflite<br/>auto-discovered at boot"]
    end

    A -->|"A"| B -->|scp| D
    A -->|"B"| C -->|scp| D
```

</details>

<br/>

1. **Export to TFLite** via `optimum-cli export tflite --model google/vit-base-patch16-224 --quantize int8`
2. **Drop the `.tflite` into `python/models/`** -- modify `face_detector_mpu.py` to match input/output signatures if different
3. **Run inference** -- the same `tflite-runtime` runs any valid TFLite model

<br/>

> **Tip:** Stick to mobile-optimized architectures (MobileNetV2/V3, EfficientNet-Lite,
> NanoDet, PicoDet). Models under 5M parameters with 320x320 input run comfortably
> on the A53 cores.

<br/>

#### Bringing a Custom Edge Impulse Model

[Edge Impulse](https://edgeimpulse.com/) trains custom ML models on your own data.
Models trained there export as TFLite and run on the Uno Q identically to AI Hub models.

<br/>

<p align="center">
  <img src="https://mermaid.ink/img/Z3JhcGggTFIKICAgIEFbIjEuIENvbGxlY3QgJiBMYWJlbDxici8-aW1hZ2VzLCBhdWRpbywgc2Vuc29yIGRhdGEiXSAtLT4gQlsiMi4gRGVzaWduIEltcHVsc2U8YnIvPnNpZ25hbCBwcm9jZXNzaW5nICs8YnIvPmxlYXJuaW5nIGJsb2NrIl0KICAgIEIgLS0-IENbIjMuIFRyYWluPGJyLz5Nb2JpbGVOZXQsIGN1c3RvbSBEU1ArTk4iXQogICAgQyAtLT4gRFsiNC4gVGVzdDxici8-bGl2ZSBjbGFzc2lmaWNhdGlvbiJdCiAgICBEIC0tPiBFWyI1LiBEZXBsb3k8YnIvPlRGTGl0ZSAoaW50OCkiXQogICAgRSAtLT4gRlsiVW5vIFE6IHB5dGhvbi9tb2RlbHMvPGJyLz5ydW5zIG9uIFFSQjIyMTAgTVBVIl0=?type=png&bgColor=!white" alt="diagram" width="700">
</p>

<details>
<summary>Diagram source (Mermaid)</summary>

```mermaid
graph LR
    A["1. Collect & Label<br/>images, audio, sensor data"] --> B["2. Design Impulse<br/>signal processing +<br/>learning block"]
    B --> C["3. Train<br/>MobileNet, custom DSP+NN"]
    C --> D["4. Test<br/>live classification"]
    D --> E["5. Deploy<br/>TFLite (int8)"]
    E --> F["Uno Q: python/models/<br/>runs on QRB2210 MPU"]
```

</details>

<br/>

> **Note:** Edge Impulse also has a direct Arduino library export (C++), but that targets
> the STM32 MCU which is too constrained for most ML models (Cortex-M33, 786 KB SRAM).
> Use the TFLite export to the MPU side instead.

<br/>

#### AI Model Ecosystem for Uno Q

<br/>

<p align="center">
  <img src="https://mermaid.ink/img/Z3JhcGggVEQKICAgIHN1YmdyYXBoIERlbW9bIlRISVMgREVNTyAod29ya3Mgb3V0IG9mIHRoZSBib3gpIl0KICAgICAgICBNUFsiR29vZ2xlIE1lZGlhUGlwZTxici8-NDc4LXB0IGZhY2UgbGFuZG1hcmtzPGJyLz5SdW5zIGluIEJST1dTRVIgdmlhIFdBU00iXQogICAgICAgIEJLWyJBcmR1aW5vIEFwcCBMYWIgQnJpY2tzPGJyLz53ZWJfdWksIG9ial9kZXQsIG1vdGlvbjxici8-UnVucyBvbiBNUFUgKERvY2tlcikiXQogICAgZW5kCgogICAgc3ViZ3JhcGggQWR2YW5jZWRbIkFEVkFOQ0VEIChyZXF1aXJlcyBhZGRpdGlvbmFsIHNldHVwKSJdCiAgICAgICAgQUhbIlF1YWxjb21tIEFJIEh1Yjxici8-MTAwKyBvcHRpbWl6ZWQgbW9kZWxzPGJyLz5SdW5zIG9uIE1QVSAodGZsaXRlLXJ1bnRpbWUpIl0KICAgICAgICBIRlsiSHVnZ2luZyBGYWNlPGJyLz41MDBrKyBtb2RlbHM8YnIvPkV4cG9ydCB0byBURkxpdGUgdmlhIG9wdGltdW0iXQogICAgICAgIEVJWyJFZGdlIEltcHVsc2U8YnIvPlRyYWluIG9uIFlPVVIgZGF0YTxici8-RXhwb3J0IHRvIFRGTGl0ZSJdCiAgICBlbmQKCiAgICBNUCAtLT4gUFlbIlB5dGhvbiBDb29yZGluYXRvciAobWFpbi5weSk8YnIvPlJlY2VpdmVzIGRhdGEgZnJvbSBBTlkgc291cmNlIl0KICAgIEJLIC0tPiBQWQogICAgQUggLS0-IFBZCiAgICBIRiAtLT4gUFkKICAgIEVJIC0tPiBQWQogICAgUFkgLS0-IEJSWyJCcmlkZ2UgUlBDIHRvIE1DVSAoTEVEL1JHQi9HUElPKSJdCiAgICBQWSAtLT4gV1NbIldlYlNvY2tldCB0byBCcm93c2VyIChVSSBvdmVybGF5KSJd?type=png&bgColor=!white" alt="diagram" width="700">
</p>

<details>
<summary>Diagram source (Mermaid)</summary>

```mermaid
graph TD
    subgraph Demo["THIS DEMO (works out of the box)"]
        MP["Google MediaPipe<br/>478-pt face landmarks<br/>Runs in BROWSER via WASM"]
        BK["Arduino App Lab Bricks<br/>web_ui, obj_det, motion<br/>Runs on MPU (Docker)"]
    end

    subgraph Advanced["ADVANCED (requires additional setup)"]
        AH["Qualcomm AI Hub<br/>100+ optimized models<br/>Runs on MPU (tflite-runtime)"]
        HF["Hugging Face<br/>500k+ models<br/>Export to TFLite via optimum"]
        EI["Edge Impulse<br/>Train on YOUR data<br/>Export to TFLite"]
    end

    MP --> PY["Python Coordinator (main.py)<br/>Receives data from ANY source"]
    BK --> PY
    AH --> PY
    HF --> PY
    EI --> PY
    PY --> BR["Bridge RPC to MCU (LED/RGB/GPIO)"]
    PY --> WS["WebSocket to Browser (UI overlay)"]
```

</details>

<br/>

#### The Decision Tree

<br/>

<p align="center">
  <img src="https://mermaid.ink/img/Z3JhcGggVEQKICAgIFExeyJOZWVkIGZhY2UgbGFuZG1hcmtzPGJyLz4oNDc4IHBvaW50cywgZXhwcmVzc2lvbnMsIGlyaXMpPyJ9CiAgICBRMSAtLT58WUVTfCBBMVsiQnJvd3Nlci1zaWRlIE1lZGlhUGlwZTxici8-KHRoaXMgZGVtbyBkZWZhdWx0KSJdCiAgICBRMSAtLT58Tk98IFEyeyJQcmUtYnVpbHQgQXBwIExhYiBCcmljazxici8-Zm9yIHlvdXIgdGFzaz8ifQogICAgUTIgLS0-fFlFU3wgQTJbIlVzZSB0aGUgQnJpY2s8YnIvPihvbmUgbGluZSBpbiBhcHAueWFtbCkiXQogICAgUTIgLS0-fE5PfCBRM3siTW9kZWwgYXZhaWxhYmxlIG9uPGJyLz5RdWFsY29tbSBBSSBIdWI_In0KICAgIFEzIC0tPnxZRVN8IEEzWyJDb21waWxlIG9wdGltaXplZCBURkxpdGU8YnIvPmZvciBRUkIyMjEwIl0KICAgIFEzIC0tPnxOT3wgUTR7Ik1vZGVsIGF2YWlsYWJsZSBvbjxici8-SHVnZ2luZyBGYWNlPyJ9CiAgICBRNCAtLT58WUVTfCBBNFsiRXhwb3J0IHRvIFRGTGl0ZSB2aWEgb3B0aW11bSw8YnIvPmRlcGxveSB0byBweXRob24vbW9kZWxzLyJdCiAgICBRNCAtLT58Tk98IFE1eyJIYXZlIHlvdXIgb3duPGJyLz50cmFpbmluZyBkYXRhPyJ9CiAgICBRNSAtLT58WUVTfCBBNVsiVHJhaW4gaW4gRWRnZSBJbXB1bHNlLDxici8-ZXhwb3J0IFRGTGl0ZSJdCiAgICBRNSAtLT58Tk98IEE2WyJDaGVjayBURiBNb2RlbCBHYXJkZW4sPGJyLz5jb252ZXJ0IHRvIFRGTGl0ZSJd?type=png&bgColor=!white" alt="diagram" width="700">
</p>

<details>
<summary>Diagram source (Mermaid)</summary>

```mermaid
graph TD
    Q1{"Need face landmarks<br/>(478 points, expressions, iris)?"}
    Q1 -->|YES| A1["Browser-side MediaPipe<br/>(this demo default)"]
    Q1 -->|NO| Q2{"Pre-built App Lab Brick<br/>for your task?"}
    Q2 -->|YES| A2["Use the Brick<br/>(one line in app.yaml)"]
    Q2 -->|NO| Q3{"Model available on<br/>Qualcomm AI Hub?"}
    Q3 -->|YES| A3["Compile optimized TFLite<br/>for QRB2210"]
    Q3 -->|NO| Q4{"Model available on<br/>Hugging Face?"}
    Q4 -->|YES| A4["Export to TFLite via optimum,<br/>deploy to python/models/"]
    Q4 -->|NO| Q5{"Have your own<br/>training data?"}
    Q5 -->|YES| A5["Train in Edge Impulse,<br/>export TFLite"]
    Q5 -->|NO| A6["Check TF Model Garden,<br/>convert to TFLite"]
```

</details>

<br/>

> In all cases, the MCU layer, Bridge providers, WebSocket events, and Python
> coordinator remain the same. **Only the inference source changes.**

<br/>

</details>

<br/>

<details>
<summary><strong>Where the Uno Q Fits in Qualcomm's World</strong></summary>

<br/>

> **Context:** The material below is background reading about Qualcomm's product
> ecosystem, the upcoming Ventuno Q, and industry trends. None of it is required
> to use this demo.

<br/>

#### Qualcomm Dragonwing IoT Processor Lineup

The QRB2210 is Qualcomm's entry-tier IoT processor:

<br/>

| Feature            | QRB2210 (Uno Q)                    | QCS6490                               | QCS8550                              |
|:-------------------|:-----------------------------------|:---------------------------------------|:-------------------------------------|
| **Series**         | Q2 (Dragonwing)                    | Q6 (Dragonwing)                        | Q8 (Dragonwing)                      |
| **CPU**            | 4x Cortex-A53 @ 2.0 GHz           | Kryo 670 (big.LITTLE)                  | Kryo (big.LITTLE)                    |
| **GPU**            | Adreno 702                         | Adreno 643                             | Adreno 740                           |
| **NPU**            | None (0 TOPS)                      | Hexagon DSP + HTA (~12 TOPS)           | Hexagon NPU (~48 TOPS)              |
| **RAM**            | 2-4 GB LPDDR4                      | Up to 8 GB LPDDR4X                     | Up to 16 GB LPDDR5X                  |
| **AI inference**   | CPU/GPU TFLite only                | NPU-accelerated (QNN, SNPE)            | NPU-accelerated (QNN)               |
| **Use case**       | Entry IoT, prototyping, education  | Mid-tier edge AI, smart cameras        | High-end edge AI, robotics          |
| **Approx. cost**   | ~$25                               | ~$80                                   | ~$150+                               |

<br/>

> _QCS6490 and QCS8550 specs are approximate. Consult
> [Qualcomm's product pages](https://www.qualcomm.com/products/technology/processors)
> for exact specifications._

<br/>

#### Uno Q vs Ventuno Q

Qualcomm announced its intent to acquire Arduino in October 2025. The combined
entity is executing a two-board hardware strategy:

<br/>

| Spec            | Arduino Uno Q (Shipping Now)                  | Arduino Ventuno Q (Announced EW 2026)         |
|:----------------|:----------------------------------------------|:----------------------------------------------|
| **MPU**         | Qualcomm QRB2210 (Q2 Series)                  | Qualcomm Dragonwing IQ8 (IQ-8275)             |
| **CPU**         | 4x Cortex-A53 @ 2.0 GHz                      | 8-core Kryo (up to ~2.4 GHz)                  |
| **GPU**         | Adreno 702                                    | Adreno                                        |
| **NPU**         | None (0 TOPS)                                 | Hexagon Tensor (~40 TOPS)                     |
| **RAM**         | 2-4 GB LPDDR4                                 | 16 GB LPDDR5                                  |
| **Storage**     | 16-64 GB eMMC                                 | 64 GB eMMC + M.2 NVMe                         |
| **MCU**         | STM32U585 (Cortex-M33, 786 KB SRAM)           | STM32H5F5 (Cortex-M33, higher SRAM)           |
| **OS**          | Debian Linux + Zephyr                         | Ubuntu/Debian + Zephyr                        |
| **Price**       | ~$90 (4 GB)                                   | ~$300 (expected)                               |
| **Best for**    | Learning, prototyping, IoT gateways           | On-device LLMs, NPU vision, robotics          |

<br/>

Both boards share: dual-brain architecture (MPU + MCU via Bridge), App Lab + Bricks
ecosystem, Arduino IDE/Cloud compatibility, Python (MPU) + C++ Sketch (MCU) programming
model, and the same Bridge API pattern.

<br/>

> _Ventuno Q specs are based on the Embedded World 2026 announcement and may change._

<br/>

#### Qualcomm's Full-Stack Edge AI Ecosystem

Assembled through acquisitions (2024-2025):

<br/>

<p align="center">
  <img src="https://mermaid.ink/img/Z3JhcGggVEQKICAgIEFbIlNJTElDT048YnIvPlF1YWxjb21tIChpbi1ob3VzZSk8YnIvPlNuYXBkcmFnb24sIERyYWdvbndpbmcsPGJyLz5IZXhhZ29uIE5QVSwgQUkgSHViIl0gLS0-IEVbIlRIRSBWSVNJT046PGJyLz5PbmUgdmVuZG9yIGZvciBjaGlwLCBtb2RlbCw8YnIvPk9TLCBPVEEsIElERSwgY2xvdWQsIGNvbW11bml0eSJdCiAgICBCWyJBSSBUT09MQ0hBSU48YnIvPkVkZ2UgSW1wdWxzZSAoYWNxLiBNYXIgMjAyNSk8YnIvPlRyYWluIGN1c3RvbSBNTCBtb2RlbHMsPGJyLz5kZXBsb3kgdG8gUXVhbGNvbW0gZGV2aWNlcyJdIC0tPiBFCiAgICBDWyJPUyArIEZMRUVUIE1HTVQ8YnIvPkZvdW5kcmllcy5pbyAoYWNxLiBNYXIgMjAyNCk8YnIvPkZvdW5kcmllc0ZhY3RvcnksIE9UQSw8YnIvPnNlY3VyZSBib290LCBDSS9DRCJdIC0tPiBFCiAgICBEWyJERVZFTE9QRVIgQ09NTVVOSVRZPGJyLz5BcmR1aW5vIChhbm5vdW5jZWQgT2N0IDIwMjUpPGJyLz4zM00rIGRldmVsb3BlcnMsIEFwcCBMYWIsPGJyLz5BcmR1aW5vIENsb3VkLCBCcmlja3MiXSAtLT4gRQ==?type=png&bgColor=!white" alt="diagram" width="700">
</p>

<details>
<summary>Diagram source (Mermaid)</summary>

```mermaid
graph TD
    A["SILICON<br/>Qualcomm (in-house)<br/>Snapdragon, Dragonwing,<br/>Hexagon NPU, AI Hub"] --> E["THE VISION:<br/>One vendor for chip, model,<br/>OS, OTA, IDE, cloud, community"]
    B["AI TOOLCHAIN<br/>Edge Impulse (acq. Mar 2025)<br/>Train custom ML models,<br/>deploy to Qualcomm devices"] --> E
    C["OS + FLEET MGMT<br/>Foundries.io (acq. Mar 2024)<br/>FoundriesFactory, OTA,<br/>secure boot, CI/CD"] --> E
    D["DEVELOPER COMMUNITY<br/>Arduino (announced Oct 2025)<br/>33M+ developers, App Lab,<br/>Arduino Cloud, Bricks"] --> E
```

</details>

<br/>

| Stage              | Tool                                  | What It Does                                       |
|:-------------------|:--------------------------------------|:---------------------------------------------------|
| **Prototype**      | Arduino IDE / App Lab                 | Write sketch + Python, test on single board        |
| **Train AI**       | Edge Impulse                          | Train custom model on your data, export TFLite     |
| **Optimize**       | AI Hub                                | Compile + quantize model for QRB2210 or IQ8        |
| **Secure OS**      | FoundriesFactory                      | Hardened Linux, secure boot, container isolation   |
| **Deploy fleet**   | FoundriesFactory + Arduino Cloud      | OTA updates to 10 or 10,000 boards                 |
| **Monitor**        | Arduino Cloud                         | Dashboard, alerts, remote management               |

<br/>

#### Qualcomm Physical AI Stack

<br/>

<p align="center">
  <img src="https://mermaid.ink/img/Z3JhcGggVEQKICAgIEFbIkFQUExJQ0FUSU9OUzxici8-SHVtYW5vaWRzLCBBTVJzLCBEcm9uZXMsPGJyLz5TbWFydCBDYW1lcmFzLCBJb1QgU2Vuc29ycyJdCiAgICBCWyJBSSBNT0RFTFM8YnIvPkFJIEh1YiwgRWRnZSBJbXB1bHNlLDxici8-SHVnZ2luZyBGYWNlLCBNZWRpYVBpcGUiXQogICAgQ1siU09GVFdBUkUgUExBVEZPUk08YnIvPkFwcCBMYWIsIEJyaWNrcywgQXJkdWlubyBDbG91ZCw8YnIvPkZvdW5kcmllc0ZhY3RvcnkiXQogICAgRFsiU0lMSUNPTiJdCgogICAgQSAtLT4gQiAtLT4gQyAtLT4gRAoKICAgIEQgLS0tIEQxWyJJUTEwIC0tIEh1bWFub2lkL0luZHVzdHJpYWwiXQogICAgRCAtLS0gRDJbIklROCAtLSBFZGdlIEFJL1JvYm90aWNzIChWRU5UVU5PIFEpIl0KICAgIEQgLS0tIEQzWyJJUTYgLS0gU21hcnQgQ2FtZXJhcyJdCiAgICBEIC0tLSBENFsiUTggLS0gSGlnaC1lbmQgSW9UIl0KICAgIEQgLS0tIEQ1WyJRNiAtLSBNaWQtdGllciBJb1QiXQogICAgRCAtLS0gRDZbIlEyIC0tIEVudHJ5IElvVCAoVU5PIFEpIl0=?type=png&bgColor=!white" alt="diagram" width="700">
</p>

<details>
<summary>Diagram source (Mermaid)</summary>

```mermaid
graph TD
    A["APPLICATIONS<br/>Humanoids, AMRs, Drones,<br/>Smart Cameras, IoT Sensors"]
    B["AI MODELS<br/>AI Hub, Edge Impulse,<br/>Hugging Face, MediaPipe"]
    C["SOFTWARE PLATFORM<br/>App Lab, Bricks, Arduino Cloud,<br/>FoundriesFactory"]
    D["SILICON"]

    A --> B --> C --> D

    D --- D1["IQ10 -- Humanoid/Industrial"]
    D --- D2["IQ8 -- Edge AI/Robotics (VENTUNO Q)"]
    D --- D3["IQ6 -- Smart Cameras"]
    D --- D4["Q8 -- High-end IoT"]
    D --- D5["Q6 -- Mid-tier IoT"]
    D --- D6["Q2 -- Entry IoT (UNO Q)"]
```

</details>

<br/>

> The face detection demo running on this Uno Q is a small example of this larger arc.
> The same architectural pattern -- camera input, AI inference, Bridge to MCU, real-time
> actuation -- is how a warehouse robot processes its environment, how a smart camera
> identifies defects, and how a drone navigates autonomously. The Uno Q teaches the
> pattern at an accessible price point.

<br/>

</details>

<br/>

---

<br/>

## Links & Resources

**Arduino Hardware & Software**

| Resource                    | Link                                                                                               |
|:----------------------------|:---------------------------------------------------------------------------------------------------|
| Arduino Uno Q Hardware      | [docs.arduino.cc/hardware/uno-q/](https://docs.arduino.cc/hardware/uno-q/)                         |
| UNO Q User Manual           | [docs.arduino.cc/tutorials/uno-q/user-manual/](https://docs.arduino.cc/tutorials/uno-q/user-manual/) |
| UNO Q Pinout (PDF)          | [ABX00162-full-pinout.pdf](https://docs.arduino.cc/resources/pinouts/ABX00162-full-pinout.pdf)      |
| UNO Q Datasheet (PDF)       | [ABX00162-ABX00173-datasheet.pdf](https://docs.arduino.cc/resources/datasheets/ABX00162-ABX00173-datasheet.pdf) |
| Arduino App Lab             | [docs.arduino.cc/software/app-lab/](https://docs.arduino.cc/software/app-lab/)                     |
| App Lab Bricks              | [docs.arduino.cc/software/app-lab/tutorials/bricks](https://docs.arduino.cc/software/app-lab/tutorials/bricks) |
| Arduino Cloud               | [docs.arduino.cc/arduino-cloud/](https://docs.arduino.cc/arduino-cloud/)                           |
| Buy Arduino Uno Q           | [store.arduino.cc/pages/uno-q](https://store.arduino.cc/pages/uno-q)                               |

<br/>

**AI & ML Platforms**

| Resource                          | Link                                                                                                        |
|:----------------------------------|:------------------------------------------------------------------------------------------------------------|
| Google MediaPipe Face Landmarker  | [ai.google.dev/edge/mediapipe](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker)       |
| Qualcomm AI Hub                   | [aihub.qualcomm.com](https://aihub.qualcomm.com/)                                                          |
| Qualcomm AI Hub Models            | [aihub.qualcomm.com/models](https://aihub.qualcomm.com/models)                                              |
| Edge Impulse                      | [edgeimpulse.com](https://edgeimpulse.com/)                                                                 |
| Hugging Face Hub                  | [huggingface.co/models](https://huggingface.co/models)                                                      |
| TensorFlow Lite Model Garden      | [tensorflow.org/lite/models](https://www.tensorflow.org/lite/models)                                         |

<br/>

**Qualcomm & Industry**

| Resource                           | Link                                                                                                       |
|:-----------------------------------|:-----------------------------------------------------------------------------------------------------------|
| Qualcomm Dragonwing Platform       | [qualcomm.com/products/technology/processors](https://www.qualcomm.com/products/technology/processors)      |
| Foundries.io / FoundriesFactory    | [foundries.io](https://foundries.io/)                                                                      |
| Arduino Ventuno Q (EW 2026)        | [blog.arduino.cc](https://blog.arduino.cc/)                                                                |

<br/>

---

<br/>

## Contributing

Contributions are welcome. If you find a bug, have a feature request, or want
to improve the documentation:

1. **Fork** this repository
2. **Create a branch** for your feature or fix (`git checkout -b feature/my-feature`)
3. **Commit** your changes with clear messages
4. **Push** to your fork and open a **Pull Request**

<br/>

> **Guideline:** Keep the architecture modular -- the inference source should remain
> swappable, and the MCU layer should stay event-driven.

<br/>

---

<br/>

## License

This project is licensed under the **MIT License** -- see the [LICENSE](LICENSE) file for details.

<br/>

---

<div align="center">

<br/>

**Built for the [Arduino Uno Q](https://store.arduino.cc/pages/uno-q/)**

**Qualcomm QRB2210 + STM32U585**

<br/>

*The inference source is swappable. The architecture is the showcase.*

<br/>

</div>
