/*
 * Wojo's Uno Q Face Outline Demo — STM32 MCU Sketch
 *
 * Runs on the STM32U585 microcontroller (MCU side).
 * Communicates with the Linux MPU (Qualcomm QRB2210) via
 * the Arduino Router Bridge for RPC-based messaging.
 *
 * Bridge RPC functions registered:
 *   face_detected(json)  — called when faces are visible
 *   no_face()            — called when no faces detected
 *   set_device_mode(str) — switches between uno_q / ventuno
 *
 * Bridge RPC calls made:
 *   mcu_ready()          — sent once after setup completes
 *   sensor_data(json)    — periodic ambient sensor readings
 */

#include <Arduino_RouterBridge.h>

#define STATUS_LED LED_BUILTIN
#define SENSOR_INTERVAL_MS 1000

bool facePresent = false;
String deviceMode = "uno_q";
unsigned long lastSensorRead = 0;

// ── Bridge RPC handlers (called from Python main.py) ─────────────

void onFaceDetected(const String& payload) {
    facePresent = true;
    digitalWrite(STATUS_LED, HIGH);
    Serial.print("[MCU] Face detected: ");
    Serial.println(payload);
}

void onNoFace() {
    facePresent = false;
    digitalWrite(STATUS_LED, LOW);
}

void onSetDeviceMode(const String& mode) {
    deviceMode = mode;
    Serial.print("[MCU] Device mode: ");
    Serial.println(deviceMode);
}

// ── Sensor reading (example: ambient light via A0) ───────────────

void readAndSendSensors() {
    int lightLevel = analogRead(A0);

    String json = "{\"light\":";
    json += lightLevel;
    json += ",\"mode\":\"";
    json += deviceMode;
    json += "\",\"face\":";
    json += facePresent ? "true" : "false";
    json += "}";

    Bridge.call("sensor_data", json);
}

// ── Setup & Loop ─────────────────────────────────────────────────

void setup() {
    Serial.begin(115200);
    pinMode(STATUS_LED, OUTPUT);
    digitalWrite(STATUS_LED, LOW);

    Bridge.begin();
    Bridge.on("face_detected", onFaceDetected);
    Bridge.on("no_face", onNoFace);
    Bridge.on("set_device_mode", onSetDeviceMode);

    Serial.println("[MCU] Wojo's Uno Q Face Demo — bridge ready");
    Bridge.call("mcu_ready");
}

void loop() {
    Bridge.update();

    unsigned long now = millis();
    if (now - lastSensorRead >= SENSOR_INTERVAL_MS) {
        lastSensorRead = now;
        readAndSendSensors();
    }
}
