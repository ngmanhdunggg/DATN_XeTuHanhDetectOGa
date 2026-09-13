#pragma once
#include <Arduino.h>

void controlBegin();
void controlLoop50ms();
void controlOnHeartbeat();

// Đầu vào từ UI/RPi: tốc độ m/s & góc đánh lái bánh xe (±30°)
void controlOnManualWS(float dc_mps, float steer_deg);
void controlOnAutoSet(float dc_mps, float steer_deg);

// Mode
void controlSetSoftAuto(bool on);
bool controlIsAuto();
void controlForceManualNeutralGate();

// Status helpers (cho Net/UI)
void controlFillStatusJSON(char* buf, size_t len);
void controlGetState(float& rpm, int& pwm, float& servoAbsDeg,
                     float& set_rpm, bool& isAuto);

bool controlIsLinkLost();