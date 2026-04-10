#include "Arduino_RouterBridge.h"
#include <Arduino_LED_Matrix.h>

Arduino_LED_Matrix matrix;

#define PIN_LED_R   (LED_BUILTIN + 3)
#define PIN_LED_G   (LED_BUILTIN + 4)
#define PIN_LED_B   (LED_BUILTIN + 5)

const uint32_t hello_face[] = {
  0x000200a8, 0x0a802000, 0x04403e00, 0x00000000
};

const uint32_t idle_face[] = {
  0x00000038, 0x0e000000, 0x00007f00, 0x00000000
};

const uint32_t surprise_face[] = {
  0x000200a8, 0x0a800000, 0x00001c00, 0x00000000
};

const uint32_t sad_face[] = {
  0x000200a8, 0x0a800000, 0x03c04200, 0x00000000
};

void setRGB(bool r, bool g, bool b) {
    digitalWrite(PIN_LED_R, r ? LOW : HIGH);
    digitalWrite(PIN_LED_G, g ? LOW : HIGH);
    digitalWrite(PIN_LED_B, b ? LOW : HIGH);
}

void setup() {
  Serial.begin(115200);
  matrix.begin();
  pinMode(LED_BUILTIN, OUTPUT);

  pinMode(PIN_LED_R, OUTPUT);
  pinMode(PIN_LED_G, OUTPUT);
  pinMode(PIN_LED_B, OUTPUT);
  setRGB(false, false, false);

  if (!Bridge.begin()) {
    Serial.println("cannot setup Bridge");
  }
  if (!Monitor.begin()) {
    Serial.println("cannot setup Monitor");
  }

  Bridge.provide("greet", greet);
  Bridge.provide("show_face", showFace);
  Bridge.provide("show_no_face", showNoFace);
  Bridge.provide("show_expression", showExpression);
  Bridge.provide("set_rgb", setRgbFromPython);

  matrix.loadFrame(idle_face);
}

void loop() {
}

void greet() {
    Monitor.print("Face detected - greeting!");
    digitalWrite(LED_BUILTIN, HIGH);
    matrix.loadFrame(hello_face);
    setRGB(false, true, false);
    delay(2000);
    digitalWrite(LED_BUILTIN, LOW);
    matrix.loadFrame(idle_face);
    setRGB(false, false, false);
}

void showFace() {
    digitalWrite(LED_BUILTIN, HIGH);
    matrix.loadFrame(hello_face);
    setRGB(false, true, false);
}

void showNoFace() {
    digitalWrite(LED_BUILTIN, LOW);
    matrix.loadFrame(idle_face);
    setRGB(true, false, false);
}

void showExpression(String expr) {
    if (expr == "smile" || expr == "happy" || expr == "neutral") {
        matrix.loadFrame(hello_face);
        setRGB(false, true, false);
    } else if (expr == "surprise" || expr == "surprised") {
        matrix.loadFrame(surprise_face);
        setRGB(false, false, true);
    } else if (expr == "eyebrow" || expr == "angry" || expr == "sad") {
        matrix.loadFrame(sad_face);
        setRGB(true, true, false);
    } else {
        matrix.loadFrame(hello_face);
        setRGB(true, false, true);
    }
}

void setRgbFromPython(String color) {
    if (color == "red")         setRGB(true, false, false);
    else if (color == "green")  setRGB(false, true, false);
    else if (color == "blue")   setRGB(false, false, true);
    else if (color == "yellow") setRGB(true, true, false);
    else if (color == "cyan")   setRGB(false, true, true);
    else if (color == "purple") setRGB(true, false, true);
    else if (color == "white")  setRGB(true, true, true);
    else if (color == "off")    setRGB(false, false, false);
}
