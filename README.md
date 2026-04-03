# uno-q-face-outline
Replit browser and webcam based face tracking outline mesh demo converted to Arduino Applab project to run on Uno Q 

This repository contains an identity-preserving smart mirror prototype designed specifically for the Arduino Uno Q (QRB2210) using the Arduino App Lab and Bricks SDK. 

The project utilizes a hybrid architecture:
* **Frontend:** Runs Google MediaPipe in the browser for zero-latency facial landmark tracking, real-time meshes, and UI animations.
* **Backend:** Runs on the Uno Q Linux partition via the Bricks framework, communicating with the Fal.ai InstantID API to generate photorealistic, zero-shot face transformations.

## Hardware Setup

* **Board:** Arduino Uno Q (QRB2210)
* **Connectivity:** USB-C Hub / Dongle
* **Camera:** Standard UVC USB Webcam connected to the hub

## API Requirements

This project requires a Fal.ai API key to process the heavy InstantID image generation.
1. Create an account at [fal.ai](https://fal.ai)
2. Generate an API key.
3. Keep this key handy to apply to your Uno Q environment.

---

## Installation: Replit to App Lab Migration

Because this repository originated in Replit, it contains a few testing files. Follow these exact steps to run it natively on the Uno Q hardware.

**1. Import the Project**
Download this repository as a `.zip` file and import it into a new workspace in the Arduino App Lab.

**2. Clean the Directory (CRITICAL)**
In Replit, an `arduino/` folder was used as a shim to mimic the hardware. The Uno Q already has the real Bricks SDK installed at the system level. **You must delete the `arduino/` folder** from your App Lab workspace, or the app will crash.

**3. Install Dependencies**
Open the App Lab terminal for your Uno Q and install the required Python packages for the image processing and API routing:
```bash
pip install requests fal-client Pillow
