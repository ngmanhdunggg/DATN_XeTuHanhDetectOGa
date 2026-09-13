#ifndef SENSORS_H
#define SENSORS_H
#include <Arduino.h>

void initSensors();
void updateUltrasonic();
float getDistanceCm(int sensorIdx);
void updateBattery();
float getBatteryVoltage();
float getBatteryPercent();
#endif