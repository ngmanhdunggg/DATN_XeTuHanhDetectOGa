#include <Arduino.h>
#include "Config.h"
#include "Control.h"
#include "Net.h"
#include "Sensors.h"

void setup(){
  Serial.begin(115200);
  controlBegin();
  netBegin();
  initSensors();
}

void loop(){
  unsigned long now = millis();

  // --- ĐIỀU KHIỂN ĐỘNG CƠ (50ms) ---
  static unsigned long lastControl = 0;
  if (now - lastControl >= 50){
    controlLoop50ms();
    lastControl = now;
  }

  // --- MẠNG WIFI (20ms) ---
  static unsigned long lastNet = 0;
  if (now - lastNet >= 20){ 
    netLoop();
    lastNet = now;
  }

  // --- CẬP NHẬT CẢM BIẾN SIÊU ÂM---
  updateUltrasonic();

  // --- CẬP NHẬT PIN ---
  static unsigned long lastBattery = 0;
  if (now - lastBattery >= 3000) {
    updateBattery();
    lastBattery = now;
  }
}