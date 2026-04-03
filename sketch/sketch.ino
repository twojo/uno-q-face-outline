/*
 * Wojo's Uno Q Face Outline Demo — STM32 MCU Sketch
 *
 * Initializes the Bridge between the STM32H747 microcontroller
 * and the Linux MPU (Qualcomm QRB2210) running the Python container.
 *
 * The Bridge library enables serial communication so the MCU
 * can send sensor telemetry to the Python application.
 */

#include <Bridge.h>

void setup() {
    Bridge.begin();
    Serial.begin(115200);
    while (!Serial) {
        ;
    }
    Serial.println("Uno Q Face Demo — MCU bridge ready");
}

void loop() {
    // Bridge communication is handled by the Python container.
    // This loop is available for future MCU-side sensor reads
    // (e.g., ambient light, proximity, IMU) that can be forwarded
    // to the web frontend via Bridge.
    delay(100);
}
