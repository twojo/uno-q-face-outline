// Wojo's Uno Q Face Outline Demo — MCU Sketch
//
// This sketch runs on the STM32U585 microcontroller inside the Uno Q.
// It receives commands from the Linux MPU via the Router Bridge and
// drives the built-in 12x8 LED matrix to reflect the current face
// tracking state.
//
// The MCU is entirely event-driven: all work happens inside Bridge
// provider callbacks. loop() stays empty because there is nothing
// to poll — the Bridge handles its own thread for incoming calls.
//
// LED Matrix capabilities used:
//   - ArduinoGraphics text scrolling (IP address, mode changes)
//   - Bitmap rendering for expression faces (smiley, surprise, etc.)
//   - Rapid flash animation when a new face first appears
//
// Note: ArduinoGraphics.h MUST be included before Arduino_LED_Matrix.h
// or text scrolling silently fails. This is a known include-order
// dependency in the ArduinoGraphics + LED Matrix stack.

#include <ArduinoGraphics.h>
#include <Arduino_LED_Matrix.h>
#include "Arduino_RouterBridge.h"

Arduino_LED_Matrix matrix;

// Built-in LED doubles as a simple face-present indicator.
#define STATUS_LED LED_BUILTIN

String deviceMode = "uno_q";
bool facePresent = false;

// --- 8x12 LED Matrix Bitmap Patterns ---
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

// --- Bridge Providers ---
// Each function below is registered with Bridge.provide() in setup(),
// making it callable from the Python side via Bridge.call().
// Provider callbacks run on a separate thread from loop(), so keep
// them short and avoid blocking for extended periods.

// Scroll a string across the matrix using ArduinoGraphics.
// Font_5x7 is the most readable at this size. The text starts
// off-screen right (column 12) and scrolls left until fully gone.
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

// Show the smiley bitmap and light the status LED to indicate
// that at least one face is currently being tracked.
void showFace() {
    facePresent = true;
    digitalWrite(STATUS_LED, HIGH);
    matrix.renderBitmap(frame_smiley, 8, 12);
}

// Show an X pattern and turn off the status LED when the camera
// loses sight of all faces.
void showNoFace() {
    facePresent = false;
    digitalWrite(STATUS_LED, LOW);
    matrix.renderBitmap(frame_no_face, 8, 12);
}

// Rapidly alternate between the smiley and a blank frame to create
// a visual "flash" effect. Called when a face first enters the frame.
// Ends with the smiley held on so the display doesn't go blank.
void flashFace(int count) {
    for (int i = 0; i < count; i++) {
        matrix.renderBitmap(frame_smiley, 8, 12);
        delay(80);
        matrix.renderBitmap(frame_blank, 8, 12);
        delay(80);
    }
    matrix.renderBitmap(frame_smiley, 8, 12);
}

// Map a named expression to its bitmap. Known expressions get a
// dedicated frame; anything else falls back to scrolling the text
// so new expressions can be added without a firmware update.
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

// Switch between simulated device profiles (uno_q / ventuno).
// Scrolls a confirmation message so the user gets visual feedback
// on the matrix that the mode change was received.
void setDeviceMode(const String& mode) {
    deviceMode = mode;
    String msg = " Mode: ";
    msg += mode;
    msg += " ";
    scrollText(msg);
}

void setup() {
    pinMode(STATUS_LED, OUTPUT);
    digitalWrite(STATUS_LED, LOW);

    matrix.begin();

    // Show a brief splash on the matrix while the Bridge initializes.
    // Font_4x6 fits "UNO" in the 12-column width without scrolling.
    matrix.beginDraw();
    matrix.stroke(0xFFFFFFFF);
    matrix.textFont(Font_4x6);
    matrix.beginText(0, 1, 0xFFFFFF);
    matrix.println("UNO");
    matrix.endText();
    matrix.endDraw();
    delay(1500);

    // Initialize the Bridge and register all providers. After this
    // point the Python side can call any of these by name.
    Bridge.begin();

    Bridge.provide("scroll_text",     scrollText);
    Bridge.provide("show_face",       showFace);
    Bridge.provide("show_no_face",    showNoFace);
    Bridge.provide("flash_face",      flashFace);
    Bridge.provide("show_expression", showExpression);
    Bridge.provide("set_device_mode", setDeviceMode);

    // Notify the MPU that the MCU is ready to receive commands.
    Bridge.call("mcu_ready");
}

void loop() {
    // Nothing here. All work is handled by Bridge provider callbacks.
}
