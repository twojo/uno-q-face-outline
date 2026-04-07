/*
 * Wojo's Uno Q Face Outline Demo — STM32 MCU Sketch
 *
 * Runs on the STM32U585 microcontroller (MCU side).
 * Communicates with the Linux MPU (Qualcomm QRB2210) via
 * the Arduino Router Bridge for RPC-based messaging.
 *
 * LED Matrix (12x8 built-in):
 *   - Scrolls the device IP address on boot
 *   - Shows a smiley face bitmap when a face is detected
 *   - Rapid-flashes the face bitmap on new detection
 *   - Shows an X pattern when no face is present
 *   - Scrolls expression text (smile, surprise, etc.)
 *
 * Bridge RPC functions provided (callable from Python):
 *   scroll_text(str)       — scroll any string across the matrix
 *   show_face()            — display smiley face bitmap
 *   show_no_face()         — display X / empty pattern
 *   flash_face(count)      — rapidly flash the face bitmap N times
 *   show_expression(str)   — scroll expression emoji/text
 *   set_device_mode(str)   — switches between uno_q / ventuno
 */

// ArduinoGraphics MUST come before Arduino_LED_Matrix
#include <ArduinoGraphics.h>
#include <Arduino_LED_Matrix.h>
#include "Arduino_RouterBridge.h"

Arduino_LED_Matrix matrix;

#define STATUS_LED LED_BUILTIN

String deviceMode = "uno_q";
bool facePresent = false;

// ── 8x12 LED Matrix Bitmap Patterns ─────────────────────────────
// 8 rows x 12 cols — 1 = LED ON, 0 = LED OFF
// Design tool: https://ledmatrix-editor.arduino.cc

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

// ── Bridge RPC Handlers (called from Python via Bridge.call) ─────

void scrollText(const String& text) {
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
    facePresent = true;
    digitalWrite(STATUS_LED, HIGH);
    matrix.renderBitmap(frame_smiley, 8, 12);
}

void showNoFace() {
    facePresent = false;
    digitalWrite(STATUS_LED, LOW);
    matrix.renderBitmap(frame_no_face, 8, 12);
}

void flashFace(int count) {
    for (int i = 0; i < count; i++) {
        matrix.renderBitmap(frame_smiley, 8, 12);
        delay(80);
        matrix.renderBitmap(frame_blank, 8, 12);
        delay(80);
    }
    matrix.renderBitmap(frame_smiley, 8, 12);
}

void showExpression(const String& expr) {
    if (expr == "surprise") {
        matrix.renderBitmap(frame_surprise, 8, 12);
    } else if (expr == "eyebrow") {
        matrix.renderBitmap(frame_eyebrows, 8, 12);
    } else if (expr == "smile") {
        matrix.renderBitmap(frame_smiley, 8, 12);
    } else {
        scrollText(expr);
    }
}

void setDeviceMode(const String& mode) {
    deviceMode = mode;
    Serial.print("[MCU] Device mode: ");
    Serial.println(deviceMode);

    String msg = " Mode: ";
    msg += mode;
    msg += " ";
    scrollText(msg);
}

// ── Setup ────────────────────────────────────────────────────────

void setup() {
    Serial.begin(115200);
    pinMode(STATUS_LED, OUTPUT);
    digitalWrite(STATUS_LED, LOW);

    matrix.begin();

    // Show startup text
    matrix.beginDraw();
    matrix.stroke(0xFFFFFFFF);
    matrix.textFont(Font_4x6);
    matrix.beginText(0, 1, 0xFFFFFF);
    matrix.println("UNO");
    matrix.endText();
    matrix.endDraw();
    delay(1500);

    Bridge.begin();

    Bridge.provide("scroll_text",     scrollText);
    Bridge.provide("show_face",       showFace);
    Bridge.provide("show_no_face",    showNoFace);
    Bridge.provide("flash_face",      flashFace);
    Bridge.provide("show_expression", showExpression);
    Bridge.provide("set_device_mode", setDeviceMode);

    Serial.println("[MCU] Wojo's Uno Q Face Demo — bridge ready");
    Bridge.call("mcu_ready");
}

// ── Loop ─────────────────────────────────────────────────────────

void loop() {
    // Event-driven via Bridge.provide — no polling needed.
    // Bridge callbacks are handled automatically.
}
