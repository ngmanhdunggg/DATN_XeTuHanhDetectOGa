#include "Sensors.h"
#include "Config.h"
#include <math.h> 

// ==================== SRF05 Ultrasonic ====================
static unsigned long lastMeasureTime[3] = {0, 0, 0};
static float lastDistance[3] = {INFINITY, INFINITY, INFINITY}; 
static int currentSensor = 0;
static const unsigned long MEASURE_INTERVAL_MS = 100;

static float measureOneSensor(int trigPin, int echoPin, unsigned long timeoutUs) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  
  long duration = pulseIn(echoPin, HIGH, timeoutUs);
  if (duration == 0) return -1.0f; 
  
  float dist = duration * SOUND_SPEED_CM_PER_US / 2.0f;
  if (dist > 400.0f) return -1.0f;
  return dist;
}

void initUltrasonic() {
  pinMode(PIN_SRF05_POTHOLE_TRIG, OUTPUT);
  pinMode(PIN_SRF05_POTHOLE_ECHO, INPUT);
  pinMode(PIN_SRF05_FRONT_TRIG, OUTPUT);
  pinMode(PIN_SRF05_FRONT_ECHO, INPUT);
  pinMode(PIN_SRF05_REAR_TRIG, OUTPUT);
  pinMode(PIN_SRF05_REAR_ECHO, INPUT);
  
  digitalWrite(PIN_SRF05_POTHOLE_TRIG, LOW);
  digitalWrite(PIN_SRF05_FRONT_TRIG, LOW);
  digitalWrite(PIN_SRF05_REAR_TRIG, LOW);
  
  for (int i = 0; i < 3; i++) {
    lastMeasureTime[i] = millis();
    lastDistance[i] = INFINITY;
  }
}

void updateUltrasonic() {
  unsigned long now = millis();
  if (now - lastMeasureTime[currentSensor] >= MEASURE_INTERVAL_MS) {
    float dist = -1.0f;
    switch (currentSensor) {
      case 0: 
        dist = measureOneSensor(PIN_SRF05_POTHOLE_TRIG, PIN_SRF05_POTHOLE_ECHO, SRF05_TIMEOUT_US);
        break;
      case 1:
        dist = measureOneSensor(PIN_SRF05_FRONT_TRIG, PIN_SRF05_FRONT_ECHO, SRF05_TIMEOUT_US);
        break;
      case 2:
        dist = measureOneSensor(PIN_SRF05_REAR_TRIG, PIN_SRF05_REAR_ECHO, SRF05_TIMEOUT_US);
        break;
    }
    if (dist >= 0) {
      lastDistance[currentSensor] = dist;
    } else {
      lastDistance[currentSensor] = INFINITY;
    }
    lastMeasureTime[currentSensor] = now;
    currentSensor = (currentSensor + 1) % 3;
  }
}

float getDistanceCm(int sensorIdx) {
  if (sensorIdx < 0 || sensorIdx >= 3) return INFINITY;
  float raw = lastDistance[sensorIdx];
  if (isinf(raw)) return INFINITY;

  // Trừ offset theo từng cảm biến
  float offset = 0.0f;
  switch (sensorIdx) {
    case 0: offset = 7.4f; break;   // ổ gà
    case 1: offset = 6.7f; break;   // trước
    case 2: offset = 4.1f; break;   // sau
  }
  float corrected = raw - offset;
  if (corrected < 0) corrected = 0;
  return corrected;
}

// ==================== Battery ====================
static float batteryVoltage = 0.0f;
static float displayedPercent = -1.0f;

// Cấu hình cửa sổ trượt cho median
static const int WINDOW_SIZE = 5;
static float window[WINDOW_SIZE];
static int windowIndex = 0;
static int windowCount = 0;

// Tham số EMA
static const float EMA_ALPHA = 0.1f;
static float filteredVoltage = 0.0f;
static int medianCount = 0;
static const int MEDIAN_THRESHOLD = 5;

// Hàm so sánh cho qsort
static int cmpFloat(const void *a, const void *b) {
    float fa = *(const float*)a;
    float fb = *(const float*)b;
    return (fa > fb) - (fa < fb);
}

void initBattery() {
    analogReadResolution(12);
    pinMode(PIN_BATTERY, INPUT);

    windowIndex = 0;
    windowCount = 0;
    medianCount = 0;
    
    // Đọc một mẫu để có giá trị tạm ban đầu
    int raw = analogRead(PIN_BATTERY);
    float voltageAtPin = (raw / 4095.0f) * 3.3f;
    float initialVoltage = (voltageAtPin / VOLTAGE_DIVIDER) * 1.030f;
    filteredVoltage = initialVoltage;
    batteryVoltage = initialVoltage;
    float percent = (batteryVoltage - BATTERY_MIN_V) / (BATTERY_MAX_V - BATTERY_MIN_V) * 100.0f;
    displayedPercent = constrain(percent, 0.0f, 100.0f);
}

void updateBattery() {
    // ========== ĐỌC ADC, CỬA SỔ TRƯỢT, MEDIAN, EMA==========
    int raw = analogRead(PIN_BATTERY);
    float voltageAtPin = (raw / 4095.0f) * 3.3f;
    float instantVoltage = (voltageAtPin / VOLTAGE_DIVIDER) * 1.030f;
    // Thêm vào cửa sổ trượt
    window[windowIndex] = instantVoltage;
    windowIndex = (windowIndex + 1) % WINDOW_SIZE;
    if (windowCount < WINDOW_SIZE) windowCount++;
    if (windowCount < WINDOW_SIZE) return;
    // Tính median
    float sorted[WINDOW_SIZE];
    memcpy(sorted, window, sizeof(float) * WINDOW_SIZE);
    qsort(sorted, WINDOW_SIZE, sizeof(float), cmpFloat);
    float median;
    if (WINDOW_SIZE % 2 == 0)
        median = (sorted[WINDOW_SIZE/2 - 1] + sorted[WINDOW_SIZE/2]) / 2.0f;
    else
        median = sorted[WINDOW_SIZE/2];
    medianCount++;
    float currentFiltered;
    if (medianCount <= MEDIAN_THRESHOLD)
        currentFiltered = median;
    else
        currentFiltered = EMA_ALPHA * median + (1 - EMA_ALPHA) * filteredVoltage;
    filteredVoltage = currentFiltered;
    
    // ==========TÍCH LŨY filteredVoltage VÀO KHAY, TÍNH TRUNG BÌNH==========
    static float avgBuffer[10];
    static int avgCount = 0;
    static float avgSum = 0.0f;
    // Thêm filteredVoltage vào khay
    avgBuffer[avgCount] = filteredVoltage;
    avgSum += filteredVoltage;
    avgCount++;
    // Nếu đã đủ 10 mẫu thì tính trung bình và cập nhật batteryVoltage
    if (avgCount >= 10) {
        float avgVoltage = avgSum / 10.0f;
        batteryVoltage = avgVoltage;
        float percent = (batteryVoltage - BATTERY_MIN_V) / (BATTERY_MAX_V - BATTERY_MIN_V) * 100.0f;
        displayedPercent = constrain(percent, 0.0f, 100.0f);
        // Reset khay để bắt đầu chu kỳ mới
        avgCount = 0;
        avgSum = 0.0f;
    }
}

float getBatteryVoltage() {
    return batteryVoltage;
}

float getBatteryPercent() {
    return displayedPercent;
}

void initSensors() {
    initUltrasonic();
    initBattery();
}