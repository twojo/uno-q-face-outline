# Wojo's Uno Q Face Outline Demo

Real-time face tracking application for the **Arduino Uno Q** (Qualcomm QRB2210 + STM32H747), built with MediaPipe Face Landmarker.

## Features

- 478-point facial landmark tracking (up to 4 faces)
- Full mesh, outline, dots, and feature overlays
- 8 emoji expression indicators per face
- Eye blink detection with color flash
- Pupil diameter measurement (Ventuno mode)
- Device simulation toggle: Uno Q vs Ventuno
- Real-time HUD with FPS, latency, yaw/pitch, blink scores

## Arduino App Lab

This repository is structured as an **Arduino App Lab** project for the Uno Q.

### Import into App Lab

1. Download this repository as a `.zip` file (Code > Download ZIP)
2. Open **Arduino App Lab** on your computer
3. Click **Import App** and select the downloaded `.zip`
4. App Lab will recognize the project structure and deploy it to your Uno Q

### Project Structure

```
├── app.yaml            # App Lab configuration
├── assets/             # WebUI frontend (served to browser)
│   ├── index.html      # Main application
│   └── qualcomm-logo.png
├── python/             # Linux MPU code (Qualcomm QRB2210)
│   └── main.py         # Serves WebUI via App Lab utilities
├── sketch/             # STM32 MCU code
│   └── sketch.ino      # Bridge initialization for MCU-MPU communication
└── README.md
```

### How It Works

- **`python/main.py`** runs on the Qualcomm QRB2210 Linux container and serves the web frontend
- **`sketch/sketch.ino`** runs on the STM32H747 MCU and initializes the Bridge for communication
- **`assets/index.html`** is the complete face tracking application (runs client-side in the browser via MediaPipe WASM)

## Links

- [Get the Uno Q 4GB](https://store.arduino.cc/collections/arduino-days-promo/products/uno-q-4gb)
- [Arduino Ventuno Q](https://www.arduino.cc/product-ventuno-q)
- [Arduino App Lab Docs](https://docs.arduino.cc/software/app-lab/)
- [Arduino App Lab GitHub](https://github.com/arduino/arduino-app-lab)

## Credits

Built with Replit 2026.03. Powered by Qualcomm QRB2210 and MediaPipe Tasks Vision.
