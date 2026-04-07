// SPDX-FileCopyrightText: Copyright (C) 2025 Wojo
//
// SPDX-License-Identifier: MIT

// Wojo's Uno Q Face Outline Demo — MCU Sketch
//
// This sketch runs on the STM32U585 microcontroller inside the Uno Q.
// It receives commands from the Linux MPU via the Router Bridge and
// drives the built-in 12x8 LED matrix, RGB LED, and status LED to
// reflect the current face tracking state.
//
// The MCU is entirely event-driven: all work happens inside Bridge
// provider callbacks. loop() stays empty because there is nothing
// to poll — the Bridge handles its own thread for incoming calls.
//
// ── Startup Sequence ──
// The boot process is deliberately verbose to help diagnose issues
// on the Uno Q, which can be picky with connectivity. Each step
// reports its status to both Serial and the LED matrix so you can
// tell what's happening even without a terminal connected.
//
//   1. Serial init + banner with board specs
//   2. Pin configuration (status LED, RGB, GPIO placeholders)
//   3. LED matrix init + "UNO" splash
//   4. RGB LED self-test (red → green → blue → off)
//   5. Bridge init + provider registration
//   6. Report memory, pin states, and provider count to Serial
//   7. Scroll "BRIDGE OK" on matrix + notify MPU
//
// ── Hardware Outputs ──
//   - 12x8 LED matrix: bitmaps, scrolling text, status messages
//   - Status LED (LED_BUILTIN): solid = face present, off = no face
//   - RGB LED (pins 11/12/13 or configurable): boot self-test,
//     face-detected pulse, expression color coding
//   - GPIO placeholders: digital pins reserved for relay, buzzer,
//     external LED strip, or Modulino accessories
//
// Note: ArduinoGraphics.h MUST be included before Arduino_LED_Matrix.h
// or text scrolling silently fails. This is a known include-order
// dependency in the ArduinoGraphics + LED Matrix stack.

#include <ArduinoGraphics.h>
#include <Arduino_LED_Matrix.h>
#include "Arduino_RouterBridge.h"

Arduino_LED_Matrix matrix;

// ── Pin Definitions ──
// Adjust these if your Uno Q board revision maps them differently.
// The STM32U585 on the Uno Q exposes standard Arduino header pins.

#define STATUS_LED  LED_BUILTIN

// RGB LED — some Uno Q boards have an onboard RGB LED on these pins.
// If your board doesn't, you can wire external LEDs to these pins
// with 220-ohm resistors. Set to -1 to disable any channel.
#define PIN_LED_R   11
#define PIN_LED_G   12
#define PIN_LED_B   13

// ── GPIO Placeholders ──
// These pins are reserved but NOT activated by default. Uncomment
// the corresponding code in setup() and the Bridge providers to
// enable them. Each placeholder shows how to wire common accessories.
//
// PIN_RELAY (D7):    Modulino Relay or generic 5V relay module.
//                    HIGH = relay energized. Use for lamps, buzzers,
//                    solenoids, or any load that triggers on face detection.
//
// PIN_EXT_LED (D6):  External LED strip data pin (e.g., WS2812B NeoPixel).
//                    Requires Adafruit_NeoPixel library if used.
//
// PIN_BUZZER (D5):   Piezo buzzer for audible face-detected alert.
//                    Use tone(PIN_BUZZER, freq, duration) to beep.
//
// PIN_AUX_1 (D4):   General-purpose digital output. Use for Modulino
//                    accessories, servo triggers, or custom circuits.
//
// PIN_AUX_2 (D3):   General-purpose digital output (PWM capable).
//                    Good for dimming an LED or driving a small motor.
#define PIN_RELAY    7
#define PIN_EXT_LED  6
#define PIN_BUZZER   5
#define PIN_AUX_1    4
#define PIN_AUX_2    3

// Set to true to enable each GPIO placeholder at boot.
// When false, the pin is configured but never driven.
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

// ── 8x12 LED Matrix Bitmap Patterns ──
// Each pattern is 8 rows by 12 columns (matching the built-in matrix).
// 1 = LED on, 0 = LED off.
// Design your own at: https://ledmatrix-editor.arduino.cc

const byte frame_smiley[8][12] = {
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    { 0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0 },
    { 0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0 },
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    { 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1 },
    { 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0 },
    { 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0 },
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 }
};

const byte frame_surprise[8][12] = {
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    { 0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0 },
    { 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0 },
    { 0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0 },
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    { 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0 },
    { 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0 },
    { 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0 }
};

const byte frame_no_face[8][12] = {
    { 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1 },
    { 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0 },
    { 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0 },
    { 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0 },
    { 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0 },
    { 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0 },
    { 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0 },
    { 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1 }
};

const byte frame_blank[8][12] = {
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 }
};

const byte frame_eyebrows[8][12] = {
    { 0, 1, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0 },
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    { 0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0 },
    { 0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0 },
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    { 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0 },
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 }
};

// Checkmark bitmap — shown briefly when a setup step succeeds.
const byte frame_check[8][12] = {
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0 },
    { 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0 },
    { 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0 },
    { 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0 },
    { 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0 },
    { 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0 },
    { 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0 }
};

// ── RGB LED Helpers ──
// The Uno Q's RGB LED can be used for at-a-glance status:
//   Red    = error or no face
//   Green  = face detected / system healthy
//   Blue   = processing / Bridge active
//   Off    = idle or RGB disabled
// These are simple digital writes (on/off). For PWM dimming,
// switch to analogWrite() on PWM-capable pins.

void setRGB(bool r, bool g, bool b) {
    if (PIN_LED_R >= 0) digitalWrite(PIN_LED_R, r ? HIGH : LOW);
    if (PIN_LED_G >= 0) digitalWrite(PIN_LED_G, g ? HIGH : LOW);
    if (PIN_LED_B >= 0) digitalWrite(PIN_LED_B, b ? HIGH : LOW);
}

void rgbOff() { setRGB(false, false, false); }

// Brief RGB pulse — useful for non-blocking visual feedback.
// Shows the color for `ms` milliseconds then turns off.
void rgbPulse(bool r, bool g, bool b, int ms) {
    setRGB(r, g, b);
    delay(ms);
    rgbOff();
}

// ── GPIO Placeholder Helpers ──
// These functions wrap the placeholder pins so you can quickly
// enable them in the Bridge providers below. Each checks its
// enable flag before driving the pin.

void triggerRelay(bool on) {
    if (enableRelay) digitalWrite(PIN_RELAY, on ? HIGH : LOW);
}

void triggerBuzzer(int freqHz, int durationMs) {
    if (enableBuzzer) {
        tone(PIN_BUZZER, freqHz, durationMs);
    }
}

void triggerAux(int pin, bool on) {
    digitalWrite(pin, on ? HIGH : LOW);
}

// ── Serial Diagnostic Helpers ──

void serialDivider() {
    Serial.println("────────────────────────────────────────────────");
}

void serialSection(const char* title) {
    Serial.println();
    serialDivider();
    Serial.print("  ");
    Serial.println(title);
    serialDivider();
}

// Report a single diagnostic line with a label and value.
void serialKV(const char* key, const String& value) {
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

// ── Bridge Providers ──
// Each function below is registered with Bridge.provide() in setup(),
// making it callable from the Python side via Bridge.call().
// Provider callbacks run on a separate thread from loop(), so keep
// them short and avoid blocking for extended periods.

void scrollText(const String& text) {
    Serial.print("[MATRIX] Scrolling: ");
    Serial.println(text);
    matrix.beginDraw();
    matrix.stroke(0xFFFFFFFF);
    matrix.textScrollSpeed(60);
    matrix.textFont(Font_5x7);
    matrix.beginText(12, 1, 0xFFFFFF);
    matrix.println(text);
    matrix.endText(SCROLL_LEFT);
    matrix.endDraw();
}

void showFace() {
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
    digitalWrite(STATUS_LED, HIGH);
    setRGB(false, true, false);
    triggerRelay(true);
    matrix.renderBitmap(frame_smiley, 8, 12);
}

void showNoFace() {
    if (facePresent) {
        unsigned long duration = (millis() - lastFaceTransition) / 1000;
        Serial.print("[FACE] Face lost after ");
        Serial.print(duration);
        Serial.println("s");
    }
    facePresent = false;
    digitalWrite(STATUS_LED, LOW);
    setRGB(true, false, false);
    triggerRelay(false);
    matrix.renderBitmap(frame_no_face, 8, 12);
}

void flashFace(int count) {
    Serial.print("[MATRIX] Flash face x");
    Serial.println(count);
    for (int i = 0; i < count; i++) {
        matrix.renderBitmap(frame_smiley, 8, 12);
        setRGB(false, true, false);
        delay(80);
        matrix.renderBitmap(frame_blank, 8, 12);
        rgbOff();
        delay(80);
    }
    matrix.renderBitmap(frame_smiley, 8, 12);
    setRGB(false, true, false);
    triggerBuzzer(1000, 100);
}

void showExpression(const String& expr) {
    Serial.print("[EXPR] ");
    Serial.println(expr);

    if (expr == "surprise") {
        matrix.renderBitmap(frame_surprise, 8, 12);
        setRGB(false, false, true);
    } else if (expr == "eyebrow") {
        matrix.renderBitmap(frame_eyebrows, 8, 12);
        setRGB(true, true, false);
    } else if (expr == "smile") {
        matrix.renderBitmap(frame_smiley, 8, 12);
        setRGB(false, true, false);
    } else {
        scrollText(expr);
        setRGB(true, false, true);
    }
}

void setDeviceMode(const String& mode) {
    deviceMode = mode;
    Serial.print("[MODE] Device mode changed to: ");
    Serial.println(mode);
    String msg = " Mode: ";
    msg += mode;
    msg += " ";
    scrollText(msg);
}

// RGB control from Python — lets the MPU set arbitrary colors
// for custom status indicators or alerts.
void setRgbFromPython(const String& color) {
    Serial.print("[RGB] Set color: ");
    Serial.println(color);
    if (color == "red")        setRGB(true, false, false);
    else if (color == "green") setRGB(false, true, false);
    else if (color == "blue")  setRGB(false, false, true);
    else if (color == "yellow") setRGB(true, true, false);
    else if (color == "cyan")  setRGB(false, true, true);
    else if (color == "magenta") setRGB(true, false, true);
    else if (color == "white") setRGB(true, true, true);
    else if (color == "off")   rgbOff();
}

// GPIO toggle from Python — lets the MPU control any placeholder pin.
// payload format: "pin:state" e.g. "7:1" to set pin 7 HIGH
void setGpioFromPython(const String& payload) {
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

// Report MCU status back to the MPU — called periodically or on demand.
// Returns a summary string with uptime, face count, memory, and pin states.
void reportStatus(const String& unused) {
    unsigned long upSec = (millis() - bootTime) / 1000;
    String report = "";
    report += "uptime_s=" + String(upSec);
    report += " faces_total=" + String(faceCount);
    report += " face_now=" + String(facePresent ? 1 : 0);
    report += " mode=" + deviceMode;
    report += " free_heap=" + String(freeMemory());
    Serial.print("[STATUS] ");
    Serial.println(report);
    Bridge.call("mcu_status_report", report);
}

// Minimal freeMemory estimate for ARM Cortex-M.
// On the STM32U585 this gives the gap between the heap top and
// the stack pointer. Not perfectly accurate but useful for tracking
// memory leaks during long-running sessions.
extern "C" char* sbrk(int incr);
int freeMemory() {
    char top;
    return &top - reinterpret_cast<char*>(sbrk(0));
}

// ── Setup ──
// The setup sequence is intentionally verbose. Each step prints its
// status to Serial and shows progress on the LED matrix. This is
// critical on the Uno Q because the board can be picky with USB
// connections and Bridge initialization timing.

void setup() {
    bootTime = millis();
    Serial.begin(115200);

    // Wait briefly for Serial to connect. On the Uno Q, the USB-C
    // connection through the QRB2210 hub can take a moment.
    delay(500);

    // ── Banner ──
    serialSection("WOJO'S UNO Q FACE OUTLINE DEMO");
    serialKV("Firmware", "Face Demo v1.0");
    serialKV("Board", "Arduino Uno Q");
    serialKV("MCU", "STM32U585 (Cortex-M33)");
    serialKV("SoC (MPU side)", "Qualcomm QRB2210");
    serialKV("LED Matrix", "12x8 built-in");
    serialKV("Compile date", __DATE__);
    serialKV("Compile time", __TIME__);
    serialKV("Arduino core", String(ARDUINO));

    // ── Pin Setup ──
    serialSection("PIN CONFIGURATION");

    pinMode(STATUS_LED, OUTPUT);
    digitalWrite(STATUS_LED, LOW);
    serialKV("STATUS_LED", String(STATUS_LED) + " (OUTPUT, LOW)");

    if (PIN_LED_R >= 0) { pinMode(PIN_LED_R, OUTPUT); digitalWrite(PIN_LED_R, LOW); }
    if (PIN_LED_G >= 0) { pinMode(PIN_LED_G, OUTPUT); digitalWrite(PIN_LED_G, LOW); }
    if (PIN_LED_B >= 0) { pinMode(PIN_LED_B, OUTPUT); digitalWrite(PIN_LED_B, LOW); }
    serialKV("RGB LED R/G/B", String(PIN_LED_R) + "/" + String(PIN_LED_G) + "/" + String(PIN_LED_B));

    // Configure GPIO placeholders as OUTPUT but don't drive them
    // unless their enable flag is set.
    pinMode(PIN_RELAY, OUTPUT);   digitalWrite(PIN_RELAY, LOW);
    pinMode(PIN_EXT_LED, OUTPUT); digitalWrite(PIN_EXT_LED, LOW);
    pinMode(PIN_BUZZER, OUTPUT);  digitalWrite(PIN_BUZZER, LOW);
    pinMode(PIN_AUX_1, OUTPUT);   digitalWrite(PIN_AUX_1, LOW);
    pinMode(PIN_AUX_2, OUTPUT);   digitalWrite(PIN_AUX_2, LOW);

    serialKV("PIN_RELAY (D7)", enableRelay ? "ENABLED" : "disabled (placeholder)");
    serialKV("PIN_EXT_LED (D6)", enableExtLed ? "ENABLED" : "disabled (placeholder)");
    serialKV("PIN_BUZZER (D5)", enableBuzzer ? "ENABLED" : "disabled (placeholder)");
    serialKV("PIN_AUX_1 (D4)", enableAux1 ? "ENABLED" : "disabled (placeholder)");
    serialKV("PIN_AUX_2 (D3)", enableAux2 ? "ENABLED" : "disabled (placeholder)");

    // ── LED Matrix Init ──
    serialSection("LED MATRIX INIT");
    Serial.println("  Initializing 12x8 LED matrix...");

    matrix.begin();

    // Show a brief splash. Font_4x6 fits "UNO" in 12 columns.
    matrix.beginDraw();
    matrix.stroke(0xFFFFFFFF);
    matrix.textFont(Font_4x6);
    matrix.beginText(0, 1, 0xFFFFFF);
    matrix.println("UNO");
    matrix.endText();
    matrix.endDraw();
    Serial.println("  Matrix OK — showing 'UNO' splash");
    delay(1200);

    // Show scrolling boot status on the matrix
    scrollText("  BOOTING...  ");
    Serial.println("  Matrix scrolled 'BOOTING...'");

    // ── RGB LED Self-Test ──
    // Cycle through red, green, blue so you can visually confirm
    // all three channels are wired correctly.
    serialSection("RGB LED SELF-TEST");
    Serial.println("  Red...");
    rgbPulse(true, false, false, 300);
    Serial.println("  Green...");
    rgbPulse(false, true, false, 300);
    Serial.println("  Blue...");
    rgbPulse(false, false, true, 300);
    Serial.println("  RGB self-test complete");

    // ── Bridge Init ──
    serialSection("BRIDGE INITIALIZATION");
    Serial.println("  Starting Router Bridge (MCU <-> MPU)...");
    Serial.println("  This connects the STM32 to the QRB2210 Linux side.");

    Bridge.begin();
    Serial.println("  Bridge.begin() OK");

    // Register all providers. Each becomes callable from Python via
    // Bridge.call("name", args).
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

    Serial.println("  9 providers registered:");
    Serial.println("    scroll_text, show_face, show_no_face,");
    Serial.println("    flash_face, show_expression, set_device_mode,");
    Serial.println("    set_rgb, set_gpio, report_status");

    // ── Boot Summary ──
    serialSection("BOOT COMPLETE");
    serialKV("Boot time", String(millis() - bootTime) + "ms");
    serialKV("Free memory", String(freeMemory()) + " bytes");
    serialKV("Device mode", deviceMode);
    serialKV("Face present", "no");
    serialKV("RGB LED", "off (ready)");
    serialKV("GPIO placeholders", "configured (all LOW)");
    Serial.println();
    Serial.println("  Waiting for MPU connection...");
    Serial.println("  (Python main.py should call Bridge.call('mcu_ready'))");
    serialDivider();
    Serial.println();

    // Show checkmark on matrix to indicate successful boot
    matrix.renderBitmap(frame_check, 8, 12);
    delay(800);

    // Scroll final status on the matrix
    scrollText("  BRIDGE OK  ");

    // Notify the MPU that the MCU is ready to receive commands.
    Bridge.call("mcu_ready");
    Serial.println("[MCU] mcu_ready sent to MPU");

    // Settle into idle state — red RGB until a face is detected
    setRGB(true, false, false);
}

void loop() {
    // Nothing here. All work is handled by Bridge provider callbacks.
    //
    // If you want to add periodic tasks (heartbeat, watchdog, sensor
    // polling), you can add them here with millis()-based timing.
    // Example:
    //
    //   static unsigned long lastHeartbeat = 0;
    //   if (millis() - lastHeartbeat >= 30000) {
    //       lastHeartbeat = millis();
    //       reportStatus("");
    //   }
}
