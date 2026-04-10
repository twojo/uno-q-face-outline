// Wojo's Uno Q Face Outline Tracker Demo -- MCU Sketch
//
// Runs on the STM32U585 microcontroller inside the Arduino Uno Q.
// Receives commands from the Linux MPU via Router Bridge and drives
// the built-in LED matrix, RGB LED, and status LED to reflect
// face tracking state.
//
// LED matrix uses loadFrame() with uint32_t[4] bitmaps (same as
// Leonardo Cavagnis' "Greetings from Uno Q" reference project).

#include "Arduino_RouterBridge.h"
#include <Arduino_LED_Matrix.h>

Arduino_LED_Matrix matrix;

#define STATUS_LED  LED_BUILTIN
#define PIN_LED_R   (LED_BUILTIN + 3)
#define PIN_LED_G   (LED_BUILTIN + 4)
#define PIN_LED_B   (LED_BUILTIN + 5)

const uint32_t face_happy[] = {
  0x000200a8, 0x0a802000, 0x04403e00, 0x00000000
};

const uint32_t face_idle[] = {
  0x00000038, 0x0e000000, 0x00007f00, 0x00000000
};

const uint32_t face_surprise[] = {
  0x000200a8, 0x0a800000, 0x00001c00, 0x00000000
};

const uint32_t face_sad[] = {
  0x000200a8, 0x0a800000, 0x03c04200, 0x00000000
};

const uint32_t face_error[] = {
  0x00000000, 0x11000a00, 0x040a0011, 0x00000000
};

String deviceMode = "uno_q";
bool facePresent = false;
unsigned long bootTime = 0;
unsigned long faceCount = 0;
unsigned long lastFaceTransition = 0;

void setRGB(bool r, bool g, bool b) {
    digitalWrite(PIN_LED_R, r ? LOW : HIGH);
    digitalWrite(PIN_LED_G, g ? LOW : HIGH);
    digitalWrite(PIN_LED_B, b ? LOW : HIGH);
}

void rgbOff() {
    setRGB(false, false, false);
}

unsigned long lastReadyRetry = 0;
int readyRetries = 0;
const int MAX_READY_RETRIES = 60;
const unsigned long READY_RETRY_INTERVAL = 3000;
volatile bool mpuAcknowledged = false;

const unsigned long MPU_HEARTBEAT_TIMEOUT_MS = 30000;
volatile unsigned long lastMpuActivity = 0;
volatile bool mpuTimedOut = false;
volatile bool sessionActive = false;

void resetMpuHeartbeat() {
    lastMpuActivity = millis();
    sessionActive = true;
    if (mpuTimedOut) {
        mpuTimedOut = false;
        Serial.println("[MCU] MPU heartbeat restored");
        matrix.loadFrame(face_idle);
        setRGB(true, false, false);
    }
}

void showFace() {
    resetMpuHeartbeat();
    if (!facePresent) {
        faceCount++;
        Serial.print("[FACE] Face appeared (#");
        Serial.print(faceCount);
        Serial.println(")");
    }
    facePresent = true;
    digitalWrite(STATUS_LED, LOW);
    setRGB(false, true, false);
    matrix.loadFrame(face_happy);
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
    matrix.loadFrame(face_idle);
}

void flashFace(int count) {
    resetMpuHeartbeat();
    for (int i = 0; i < count; i++) {
        digitalWrite(STATUS_LED, LOW);
        matrix.loadFrame(face_happy);
        setRGB(false, true, false);
        delay(80);
        digitalWrite(STATUS_LED, HIGH);
        rgbOff();
        delay(80);
    }
    if (facePresent) {
        digitalWrite(STATUS_LED, LOW);
        matrix.loadFrame(face_happy);
        setRGB(false, true, false);
    }
}

void showExpression(String expr) {
    resetMpuHeartbeat();
    Serial.print("[EXPR] ");
    Serial.println(expr);

    if (expr == "smile" || expr == "happy" || expr == "neutral") {
        matrix.loadFrame(face_happy);
        setRGB(false, true, false);
    } else if (expr == "surprise" || expr == "surprised") {
        matrix.loadFrame(face_surprise);
        setRGB(false, false, true);
    } else if (expr == "eyebrow" || expr == "angry" || expr == "sad") {
        matrix.loadFrame(face_sad);
        setRGB(true, true, false);
    } else {
        matrix.loadFrame(face_happy);
        setRGB(true, false, true);
    }
}

void setDeviceMode(String mode) {
    resetMpuHeartbeat();
    deviceMode = mode;
    Serial.print("[MODE] ");
    Serial.println(mode);
}

void setRgbFromPython(String color) {
    resetMpuHeartbeat();
    if (color == "red")         setRGB(true, false, false);
    else if (color == "green")  setRGB(false, true, false);
    else if (color == "blue")   setRGB(false, false, true);
    else if (color == "yellow") setRGB(true, true, false);
    else if (color == "cyan")   setRGB(false, true, true);
    else if (color == "purple") setRGB(true, false, true);
    else if (color == "white")  setRGB(true, true, true);
    else if (color == "off")    rgbOff();
}

void setGpioFromPython(String payload) {
    resetMpuHeartbeat();
    int sep = payload.indexOf(':');
    if (sep < 0) return;
    int pin = payload.substring(0, sep).toInt();
    int val = payload.substring(sep + 1).toInt();
    digitalWrite(pin, val ? HIGH : LOW);
}

void reportStatus() {
    resetMpuHeartbeat();
    String s = "mode=" + deviceMode +
               ",face=" + String(facePresent ? "yes" : "no") +
               ",count=" + String(faceCount) +
               ",uptime=" + String((millis() - bootTime) / 1000);
    Bridge.call("status_report", s.c_str());
}

void scrollText(String text) {
    resetMpuHeartbeat();
    Serial.print("[SCROLL] ");
    Serial.println(text);
}

void onMpuAck() {
    mpuAcknowledged = true;
    lastMpuActivity = millis();
    Serial.println("[MCU] MPU acknowledged mcu_ready");
    setRGB(false, true, false);
    delay(200);
    setRGB(true, false, false);
}

void setup() {
    bootTime = millis();
    Serial.begin(115200);
    matrix.begin();
    pinMode(LED_BUILTIN, OUTPUT);

    pinMode(PIN_LED_R, OUTPUT);
    pinMode(PIN_LED_G, OUTPUT);
    pinMode(PIN_LED_B, OUTPUT);
    rgbOff();

    if (!Bridge.begin()) {
        Serial.println("cannot setup Bridge");
    }
    if (!Monitor.begin()) {
        Serial.println("cannot setup Monitor");
    }

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

    matrix.loadFrame(face_idle);

    Bridge.call("mcu_ready");
    Serial.println("[MCU] mcu_ready sent");

    setRGB(true, false, false);
}

void loop() {
    unsigned long now = millis();

    if (!mpuAcknowledged && readyRetries < MAX_READY_RETRIES) {
        if (now - lastReadyRetry >= READY_RETRY_INTERVAL) {
            lastReadyRetry = now;
            readyRetries++;
            Bridge.call("mcu_ready");
        }
    }

    if (mpuAcknowledged && sessionActive && !mpuTimedOut &&
        (now - lastMpuActivity >= MPU_HEARTBEAT_TIMEOUT_MS)) {
        mpuTimedOut = true;
        Serial.println("[MCU] MPU heartbeat timeout");
        matrix.loadFrame(face_error);
        setRGB(true, false, true);
        facePresent = false;
        digitalWrite(STATUS_LED, HIGH);
    }
}
