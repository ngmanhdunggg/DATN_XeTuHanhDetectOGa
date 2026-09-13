#include "Control_Safety.h"
#include "Config.h"
#include "Sensors.h"
#include <WiFi.h>
#include <math.h>

bool isWifiStrongEnough() {
    int rssi = WiFi.RSSI();
    return (rssi >= RSSI_WEAK_THRESHOLD);
}

float applySafetyLimit(float desired_mps) {
    float front_cm = getDistanceCm(1);   // cảm biến trước
    float rear_cm  = getDistanceCm(2);   // cảm biến sau
    const float FRONT_STOP = 10.0f;   // dừng hẳn nếu < 10cm
    const float FRONT_SAFE = 30.0f;  // bắt đầu giảm tốc khi < 30cm
    const float REAR_STOP  = 10.0f;
    const float REAR_SAFE  = 30.0f;
    if (desired_mps > 0.0f) {
        if (isinf(front_cm) || front_cm <= 0) return desired_mps; 
        if (front_cm <= FRONT_STOP) return 0.0f;
        if (front_cm >= FRONT_SAFE) return desired_mps;
        float factor = (front_cm - FRONT_STOP) / (FRONT_SAFE - FRONT_STOP);
        return desired_mps * factor;
    }
    else if (desired_mps < 0.0f) {
        if (isinf(rear_cm) || rear_cm <= 0) return desired_mps;
        if (rear_cm <= REAR_STOP) return 0.0f;
        if (rear_cm >= REAR_SAFE) return desired_mps;
        float factor = (rear_cm - REAR_STOP) / (REAR_SAFE - REAR_STOP);
        return desired_mps * factor;
    }
    return desired_mps;   
}