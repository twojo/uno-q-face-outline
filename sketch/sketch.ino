// SPDX-FileCopyrightText: Copyright (C) 2025 Wojo
//
// SPDX-License-Identifier: MIT

// Wojo's Uno Q Face Outline Demo -- MCU Sketch
//
// This sketch runs on the STM32U585 microcontroller inside the Uno Q.
// It receives commands from the Linux MPU via the Router Bridge and
// drives the built-in 13x8 LED matrix, RGB LEDs, and status LED to
// reflect the current face tracking state.
//
// The MCU is primarily event-driven: face/expression/RGB/GPIO work
// happens inside Bridge provider callbacks. loop() handles two
// housekeeping tasks: retrying the mcu_ready handshake until the MPU
// acknowledges, and monitoring for MPU heartbeat timeout after an
// active session begins.
//
// -- Startup Sequence --
//   1. Serial init + banner with board specs
//   2. Pin configuration (status LED, RGB, GPIO placeholders)
//   3. LED matrix init + smiley splash
//   4. RGB LED self-test (red -> green -> blue -> off)
//   5. Bridge init + provider registration
//   6. Report pin states and provider count to Serial
//   7. Show checkmark on matrix + notify MPU
//
// -- Hardware Outputs --
//   - 13x8 LED matrix: grayscale bitmaps, status patterns
//   - Status LED (LED_BUILTIN): solid = face present, off = no face
//   - RGB LEDs: LED4 (digital on/off) for status colors
//   - GPIO placeholders: digital pins reserved for relay, buzzer,
//     external LED strip, or Modulino accessories
//
// Aligned with official app-bricks-examples conventions (April 2026).
// No ArduinoGraphics -- the Zephyr platform does not support it.

#include <Arduino_LED_Matrix.h>
#include <Arduino_RouterBridge.h>

Arduino_LED_Matrix matrix;

// -- Pin Definitions --
// On the Uno Q, LED4 is a simple digital ON/OFF RGB LED.
// LED_BUILTIN maps to LED3_R. LED4_R/G/B are LED_BUILTIN+3/4/5.
// HIGH = OFF, LOW = ON for LED4 (active-low).
#define STATUS_LED  LED_BUILTIN
#define PIN_LED_R   (LED_BUILTIN + 3)
#define PIN_LED_G   (LED_BUILTIN + 4)
#define PIN_LED_B   (LED_BUILTIN + 5)

// -- GPIO Placeholders --
// Reserved but NOT activated by default. Set enable flags to true
// and uncomment the corresponding code to use them.
#define PIN_RELAY    D7
#define PIN_EXT_LED  D6
#define PIN_BUZZER   D5
#define PIN_AUX_1    D4
#define PIN_AUX_2    D3

bool enableRelay   = false;
bool enableExtLed  = false;
bool enableBuzzer  = false;
bool enableAux1    = false;
bool enableAux2    = false;

String deviceMode = "uno_q";
bool facePresent = false;
unsigned long bootTime = 0;
unsigned long faceCount = 0;
unsigned long lastFaceTransition = 0;

// -- 13x8 LED Matrix Bitmap Patterns (flat uint8_t grayscale) --
// Each frame is 104 values (8 rows x 13 columns).
// Values: 0 = off, 7 = brightest (3-bit grayscale).
// Use matrix.draw() to display. Requires setGrayscaleBits(3).

uint8_t frame_smiley[104] = {
    0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,7,7,0,0,0,7,7,0,0,0,
    0,0,0,7,7,0,0,0,7,7,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,
    7,0,0,0,0,0,0,0,0,0,0,0,7,
    0,7,0,0,0,0,0,0,0,0,0,7,0,
    0,0,7,7,7,7,7,7,7,7,7,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0
};

uint8_t frame_surprise[104] = {
    0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,7,7,0,0,0,7,7,0,0,0,
    0,0,7,0,0,7,0,7,0,0,7,0,0,
    0,0,0,7,7,0,0,0,7,7,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,7,7,7,7,7,0,0,0,0,
    0,0,0,0,7,0,0,0,7,0,0,0,0,
    0,0,0,0,7,7,7,7,7,0,0,0,0
};

uint8_t frame_no_face[104] = {
    7,0,0,0,0,0,0,0,0,0,0,0,7,
    0,7,0,0,0,0,0,0,0,0,0,7,0,
    0,0,7,0,0,0,0,0,0,0,7,0,0,
    0,0,0,7,0,0,0,0,0,7,0,0,0,
    0,0,0,7,0,0,0,0,0,7,0,0,0,
    0,0,7,0,0,0,0,0,0,0,7,0,0,
    0,7,0,0,0,0,0,0,0,0,0,7,0,
    7,0,0,0,0,0,0,0,0,0,0,0,7
};

uint8_t frame_blank[104] = {0};

uint8_t frame_eyebrows[104] = {
    0,0,7,7,7,0,0,0,7,7,7,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,7,7,0,0,0,7,7,0,0,0,
    0,0,0,7,7,0,0,0,7,7,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,7,7,7,7,7,7,7,7,7,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0
};

uint8_t frame_check[104] = {
    0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,7,0,
    0,0,0,0,0,0,0,0,0,0,7,0,0,
    0,0,0,0,0,0,0,0,0,7,0,0,0,
    0,7,0,0,0,0,0,0,7,0,0,0,0,
    0,0,7,0,0,0,0,7,0,0,0,0,0,
    0,0,0,7,0,0,7,0,0,0,0,0,0,
    0,0,0,0,7,7,0,0,0,0,0,0,0
};

uint8_t frame_boot[104] = {
    0,0,0,0,0,7,7,7,0,0,0,0,0,
    0,0,0,0,7,0,0,0,7,0,0,0,0,
    0,0,0,0,7,0,0,0,7,0,0,0,0,
    0,0,0,0,0,7,7,7,0,0,0,0,0,
    0,0,0,0,0,7,7,7,0,0,0,0,0,
    0,0,0,0,7,0,0,0,7,0,0,0,0,
    0,0,0,0,7,0,0,0,7,0,0,0,0,
    0,0,0,0,0,7,7,7,0,0,0,0,0
};

// -- RGB LED Helpers --
// LED4 on the Uno Q is active-low: LOW = ON, HIGH = OFF.
void setRGB(bool r, bool g, bool b) {
    digitalWrite(PIN_LED_R, r ? LOW : HIGH);
    digitalWrite(PIN_LED_G, g ? LOW : HIGH);
    digitalWrite(PIN_LED_B, b ? LOW : HIGH);
}

void rgbOff() { setRGB(false, false, false); }

void rgbPulse(bool r, bool g, bool b, int ms) {
    setRGB(r, g, b);
    delay(ms);
    rgbOff();
}

// -- GPIO Placeholder Helpers --
void triggerRelay(bool on) {
    if (enableRelay) digitalWrite(PIN_RELAY, on ? HIGH : LOW);
}

void playTone(uint8_t pin, uint32_t freqHz, uint32_t durationMs) {
    if (freqHz == 0) return;
    uint32_t halfPeriod = 500000UL / freqHz;
    uint32_t cycles = (freqHz * durationMs) / 1000;
    for (uint32_t i = 0; i < cycles; i++) {
        digitalWrite(pin, HIGH);
        delayMicroseconds(halfPeriod);
        digitalWrite(pin, LOW);
        delayMicroseconds(halfPeriod);
    }
}

void triggerBuzzer(int freqHz, int durationMs) {
    if (enableBuzzer) {
        playTone(PIN_BUZZER, freqHz, durationMs);
    }
}

// -- Serial Diagnostic Helpers --

void serialDivider() {
    Serial.println("------------------------------------------------");
}

void serialSection(const char* title) {
    Serial.println();
    serialDivider();
    Serial.print("  ");
    Serial.println(title);
    serialDivider();
}

void serialKV(const char* key, String value) {
    Serial.print("  ");
    Serial.print(key);
    for (int i = strlen(key); i < 22; i++) Serial.print(" ");
    Serial.print(": ");
    Serial.println(value);
}

void serialKV(const char* key, int value) {
    serialKV(key, String(value));
}

void serialKV(const char* key, unsigned long value) {
    serialKV(key, String(value));
}

// -- Bridge Providers --
// Each function below is registered with Bridge.provide() in setup(),
// making it callable from the Python side via Bridge.call().
// Provider callbacks run on a separate thread from loop(), so keep
// them short and avoid blocking for extended periods.

void showFace() {
    resetMpuHeartbeat();
    if (!facePresent) {
        faceCount++;
        lastFaceTransition = millis();
        Serial.print("[FACE] Face appeared (#");
        Serial.print(faceCount);
        Serial.print(") at uptime ");
        Serial.print((millis() - bootTime) / 1000);
        Serial.println("s");
    }
    facePresent = true;
    digitalWrite(STATUS_LED, LOW);
    setRGB(false, true, false);
    triggerRelay(true);
    matrix.draw(frame_smiley);
}

void showNoFace() {
    resetMpuHeartbeat();
    if (facePresent) {
        unsigned long duration = (millis() - lastFaceTransition) / 1000;
        Serial.print("[FACE] Face lost after ");
        Serial.print(duration);
        Serial.println("s");
    }
    facePresent = false;
    digitalWrite(STATUS_LED, HIGH);
    setRGB(true, false, false);
    triggerRelay(false);
    matrix.draw(frame_no_face);
}

void flashFace(int count) {
    resetMpuHeartbeat();
    Serial.print("[MATRIX] Flash face x");
    Serial.println(count);
    for (int i = 0; i < count; i++) {
        matrix.draw(frame_smiley);
        setRGB(false, true, false);
        delay(80);
        matrix.draw(frame_blank);
        rgbOff();
        delay(80);
    }
    matrix.draw(frame_smiley);
    setRGB(false, true, false);
    triggerBuzzer(1000, 100);
}

void showExpression(String expr) {
    resetMpuHeartbeat();
    Serial.print("[EXPR] ");
    Serial.println(expr);

    if (expr == "surprise") {
        matrix.draw(frame_surprise);
        setRGB(false, false, true);
    } else if (expr == "eyebrow") {
        matrix.draw(frame_eyebrows);
        setRGB(true, true, false);
    } else if (expr == "smile") {
        matrix.draw(frame_smiley);
        setRGB(false, true, false);
    } else {
        matrix.draw(frame_smiley);
        setRGB(true, false, true);
    }
}

void setDeviceMode(String mode) {
    resetMpuHeartbeat();
    deviceMode = mode;
    Serial.print("[MODE] Device mode changed to: ");
    Serial.println(mode);
}

void setRgbFromPython(String color) {
    resetMpuHeartbeat();
    Serial.print("[RGB] Set color: ");
    Serial.println(color);
    if (color == "red")         setRGB(true, false, false);
    else if (color == "green")  setRGB(false, true, false);
    else if (color == "blue")   setRGB(false, false, true);
    else if (color == "yellow") setRGB(true, true, false);
    else if (color == "cyan")   setRGB(false, true, true);
    else if (color == "magenta")setRGB(true, false, true);
    else if (color == "white")  setRGB(true, true, true);
    else if (color == "off")    rgbOff();
}

void setGpioFromPython(String payload) {
    resetMpuHeartbeat();
    Serial.print("[GPIO] Command: ");
    Serial.println(payload);
    int sep = payload.indexOf(':');
    if (sep < 0) {
        Serial.println("[GPIO] Bad format (expected pin:state)");
        return;
    }
    int pin = payload.substring(0, sep).toInt();
    int state = payload.substring(sep + 1).toInt();

    bool allowed = false;
    if (pin == PIN_RELAY   && enableRelay)  allowed = true;
    if (pin == PIN_EXT_LED && enableExtLed) allowed = true;
    if (pin == PIN_BUZZER  && enableBuzzer) allowed = true;
    if (pin == PIN_AUX_1   && enableAux1)   allowed = true;
    if (pin == PIN_AUX_2   && enableAux2)   allowed = true;

    if (!allowed) {
        Serial.print("[GPIO] Pin ");
        Serial.print(pin);
        Serial.println(" BLOCKED (not in allowlist or disabled)");
        return;
    }

    Serial.print("[GPIO] Pin ");
    Serial.print(pin);
    Serial.print(" -> ");
    Serial.println(state ? "HIGH" : "LOW");
    digitalWrite(pin, state ? HIGH : LOW);
}

void reportStatus() {
    resetMpuHeartbeat();
    unsigned long upSec = (millis() - bootTime) / 1000;
    String report = "";
    report += "uptime_s=" + String(upSec);
    report += " faces_total=" + String(faceCount);
    report += " face_now=" + String(facePresent ? 1 : 0);
    report += " mode=" + deviceMode;
    Serial.print("[STATUS] ");
    Serial.println(report);
    Bridge.call("mcu_status_report", report.c_str());
}

void scrollText(String text) {
    resetMpuHeartbeat();
    Serial.print("[MATRIX] Text: ");
    Serial.println(text);
    matrix.draw(frame_smiley);
}

// -- Setup --
void setup() {
    bootTime = millis();
    Serial.begin(115200);
    delay(500);

    // -- Banner --
    serialSection("WOJO'S UNO Q FACE OUTLINE DEMO");
    serialKV("Firmware", "Face Demo v1.0");
    serialKV("Board", "Arduino Uno Q");
    serialKV("MCU", "STM32U585 (Cortex-M33)");
    serialKV("SoC (MPU side)", "Qualcomm QRB2210");
    serialKV("LED Matrix", "13x8 built-in");
    serialKV("Compile date", __DATE__);
    serialKV("Compile time", __TIME__);
    serialKV("Arduino core", String(ARDUINO));

    // -- Pin Setup --
    serialSection("PIN CONFIGURATION");

    pinMode(STATUS_LED, OUTPUT);
    digitalWrite(STATUS_LED, HIGH);
    serialKV("STATUS_LED", String(STATUS_LED) + " (OUTPUT, OFF)");

    pinMode(PIN_LED_R, OUTPUT);
    pinMode(PIN_LED_G, OUTPUT);
    pinMode(PIN_LED_B, OUTPUT);
    rgbOff();
    serialKV("RGB LED4 R/G/B", String(PIN_LED_R) + "/" + String(PIN_LED_G) + "/" + String(PIN_LED_B));

    pinMode(PIN_RELAY, OUTPUT);   digitalWrite(PIN_RELAY, LOW);
    pinMode(PIN_EXT_LED, OUTPUT); digitalWrite(PIN_EXT_LED, LOW);
    pinMode(PIN_BUZZER, OUTPUT);  digitalWrite(PIN_BUZZER, LOW);
    pinMode(PIN_AUX_1, OUTPUT);   digitalWrite(PIN_AUX_1, LOW);
    pinMode(PIN_AUX_2, OUTPUT);   digitalWrite(PIN_AUX_2, LOW);

    serialKV("PIN_RELAY (D7)", enableRelay ? "ENABLED" : "disabled");
    serialKV("PIN_EXT_LED (D6)", enableExtLed ? "ENABLED" : "disabled");
    serialKV("PIN_BUZZER (D5)", enableBuzzer ? "ENABLED" : "disabled");
    serialKV("PIN_AUX_1 (D4)", enableAux1 ? "ENABLED" : "disabled");
    serialKV("PIN_AUX_2 (D3)", enableAux2 ? "ENABLED" : "disabled");

    // -- LED Matrix Init --
    serialSection("LED MATRIX INIT");
    Serial.println("  Initializing 13x8 LED matrix...");

    matrix.begin();
    matrix.setGrayscaleBits(3);
    matrix.clear();

    matrix.draw(frame_smiley);
    Serial.println("  Matrix OK -- showing smiley splash");
    delay(1200);

    matrix.draw(frame_boot);
    Serial.println("  Matrix showing boot icon");
    delay(800);

    // -- RGB LED Self-Test --
    serialSection("RGB LED SELF-TEST");
    Serial.println("  Red...");
    rgbPulse(true, false, false, 300);
    Serial.println("  Green...");
    rgbPulse(false, true, false, 300);
    Serial.println("  Blue...");
    rgbPulse(false, false, true, 300);
    Serial.println("  RGB self-test complete");

    // -- Bridge Init --
    serialSection("BRIDGE INITIALIZATION");
    Serial.println("  Starting Router Bridge (MCU <-> MPU)...");

    Bridge.begin();
    Serial.println("  Bridge.begin() OK");

    Serial.println("  Registering Bridge providers...");

    Bridge.provide("scroll_text",     scrollText);
    Bridge.provide("show_face",       showFace);
    Bridge.provide("show_no_face",    showNoFace);
    Bridge.provide("flash_face",      flashFace);
    Bridge.provide("show_expression", showExpression);
    Bridge.provide("set_device_mode", setDeviceMode);
    Bridge.provide("set_rgb",         setRgbFromPython);
    Bridge.provide("set_gpio",        setGpioFromPython);
    Bridge.provide("report_status",   reportStatus);
    Bridge.provide("mpu_ack",         onMpuAck);

    Serial.println("  10 providers registered:");
    Serial.println("    scroll_text, show_face, show_no_face,");
    Serial.println("    flash_face, show_expression, set_device_mode,");
    Serial.println("    set_rgb, set_gpio, report_status, mpu_ack");

    // -- Boot Summary --
    serialSection("BOOT COMPLETE");
    serialKV("Boot time", String(millis() - bootTime) + "ms");
    serialKV("Device mode", deviceMode);
    serialKV("Face present", "no");
    serialKV("RGB LED", "off (ready)");
    Serial.println();
    Serial.println("  Waiting for MPU connection...");
    serialDivider();
    Serial.println();

    matrix.draw(frame_check);
    delay(800);

    Bridge.call("mcu_ready");
    Serial.println("[MCU] mcu_ready sent to MPU");

    setRGB(true, false, false);
}

unsigned long lastReadyRetry = 0;
int readyRetries = 0;
const int MAX_READY_RETRIES = 60;
const unsigned long READY_RETRY_INTERVAL = 3000;
volatile bool mpuAcknowledged = false;

// -- MPU Heartbeat Timeout --
// After handshake, if no Bridge call is received within this interval
// the MCU assumes the MPU has crashed or disconnected and resets to
// an error state. Any Bridge provider callback resets the timer.
// The timeout only starts AFTER the first face-related Bridge call
// (not immediately after mpu_ack), so idle periods without any face
// traffic do not false-trigger the timeout.
const unsigned long MPU_HEARTBEAT_TIMEOUT_MS = 30000;
volatile unsigned long lastMpuActivity = 0;
volatile bool mpuTimedOut = false;
volatile bool sessionActive = false;

// Error pattern: alternating X with blank (visual "lost connection")
uint8_t frame_error[104] = {
    7,0,0,0,0,0,7,0,0,0,0,0,7,
    0,7,0,0,0,7,0,7,0,0,0,7,0,
    0,0,7,0,7,0,0,0,7,0,7,0,0,
    0,0,0,7,0,0,0,0,0,7,0,0,0,
    0,0,7,0,7,0,0,0,7,0,7,0,0,
    0,7,0,0,0,7,0,7,0,0,0,7,0,
    7,0,0,0,0,0,7,0,0,0,0,0,7,
    0,0,0,0,0,0,0,0,0,0,0,0,0
};

void resetMpuHeartbeat() {
    lastMpuActivity = millis();
    sessionActive = true;
    if (mpuTimedOut) {
        mpuTimedOut = false;
        Serial.println("[MCU] MPU heartbeat restored — resuming normal operation");
        setRGB(true, false, false);
        matrix.draw(frame_check);
    }
}

void onMpuAck() {
    mpuAcknowledged = true;
    lastMpuActivity = millis();
    Serial.println("[MCU] MPU acknowledged mcu_ready — retries stopped");
    setRGB(false, true, false);
    delay(200);
    setRGB(true, false, false);
}

void loop() {
    unsigned long now = millis();

    if (!mpuAcknowledged && readyRetries < MAX_READY_RETRIES) {
        if (now - lastReadyRetry >= READY_RETRY_INTERVAL) {
            lastReadyRetry = now;
            readyRetries++;
            Serial.print("[MCU] Re-sending mcu_ready (retry ");
            Serial.print(readyRetries);
            Serial.print("/");
            Serial.print(MAX_READY_RETRIES);
            Serial.println(")");
            Bridge.call("mcu_ready");
        }
    }

    if (mpuAcknowledged && sessionActive && !mpuTimedOut &&
        (now - lastMpuActivity >= MPU_HEARTBEAT_TIMEOUT_MS)) {
        mpuTimedOut = true;
        Serial.print("[MCU] MPU heartbeat timeout (");
        Serial.print(MPU_HEARTBEAT_TIMEOUT_MS / 1000);
        Serial.println("s) — showing error pattern");
        matrix.draw(frame_error);
        setRGB(true, false, true);
        facePresent = false;
        digitalWrite(STATUS_LED, HIGH);
        triggerRelay(false);
    }
}
