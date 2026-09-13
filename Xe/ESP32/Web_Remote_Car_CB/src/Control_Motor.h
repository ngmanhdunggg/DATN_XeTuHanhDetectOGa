#pragma once
#include <Arduino.h>

void motorHardwareBegin();
void motorDrivePWM(int pwm);
void motorBrake();
long getEncoderCount(); 

extern int g_lastPwm;