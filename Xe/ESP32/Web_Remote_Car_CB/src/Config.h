#pragma once
#include <Arduino.h>

// ====== Pins ======
static const int PIN_RPWM   = 25;
static const int PIN_LPWM   = 26;
static const int PIN_REN    = 27;
static const int PIN_LEN    = 14;
static const int PIN_ENC_A  = 32;
static const int PIN_ENC_B  = 33;
static const int PIN_SERVO  = 15;

// ====== UART ======
#define RPI_SERIAL          Serial1 
static const int PIN_TX1    = 17; 
static const int PIN_RX1    = 16; 
static const int UART_BAUD  = 115200;

// ====== Encoder ======
static const int ENCODER_COUNTS_PER_REV = 618; 

// ====== Wheel & Units ======
static constexpr float WHEEL_DIAM_M = 0.075f; 
static constexpr float RPM2MPS      = (float)M_PI * WHEEL_DIAM_M / 60.0f; 
static constexpr float MPS2RPM      = 1.0f / RPM2MPS;                     

// ====== Limits ======
static constexpr float MAX_MPS       = 0.70f;   
static constexpr float MAX_STEER_DEG = 30.0f;   
static constexpr float DEAD_MPS      = 0.02f;   
static constexpr float DEAD_SERVO_DEG= 0.5f;

// ====== Servo geometry ======
static constexpr float SERVO_MIN    = 41.0f;
static constexpr float SERVO_MAX    = 135.0f;
static constexpr float SERVO_CENTER = 88.0f;
static constexpr float SERVO_RATE_DPS = 90.0f;  
static constexpr float STEER_TO_SERVO = 47.0f / 30.0f;  
static constexpr float SERVO_TO_STEER = 1.0f / STEER_TO_SERVO;

// ====== PWM/Motor ======
static const int CH_RPWM   = 4;
static const int CH_LPWM   = 5;
static const int PWM_FREQ  = 20000; 
static const int PWM_BITS  = 8;     
static const int PWM_DEADBAND = 5;

// ====== PID ======
//static float Kp=1.5f, Ki=0.3f, Kd=0.05f;
static float Kp=1.86f, Ki=4.5f, Kd=0.046f;
// ====== Filters / timing ======
static const int   FILTER_SIZE = 10;
static const float LOOP_DT_S   = 0.050f; 

// ====== Safety ======
static const unsigned long TIMEOUT_MS = 2000;
static const int RSSI_WEAK_THRESHOLD = -75;


// ====== Auto-hold ======
static constexpr float HOLD_RPM_TH         = 0.30f;
static const unsigned long HOLD_PERIOD_MS  = 100;
static const int           HOLD_INIT_PWM   = 15;
static const int           HOLD_ADJ_STEP   = 3;
static const int           HOLD_MAX_PWM    = 80;
static const unsigned long HOLD_ARM_MS     = 500;
static const unsigned long HOLD_SP0_MS     = 1000;
static const int           HOLD_MIN_PWM    = 35;

//====== WiFi Station ======
static const char* WIFI_SSID = "Remote";
static const char* WIFI_PSK  = "dung28092003";

// ====== Ultrasonic SRF05 ======
// Cảm biến 1: đo ổ gà
static const int PIN_SRF05_POTHOLE_TRIG = 18;
static const int PIN_SRF05_POTHOLE_ECHO = 19;

// Cảm biến 2: phía trước
static const int PIN_SRF05_FRONT_TRIG = 21;
static const int PIN_SRF05_FRONT_ECHO = 22;

// Cảm biến 3: phía sau (ECHO dùng GPIO5)
static const int PIN_SRF05_REAR_TRIG = 23;
static const int PIN_SRF05_REAR_ECHO = 5;

static const float SOUND_SPEED_CM_PER_US = 0.0343f;   // 343 m/s
static const unsigned long SRF05_TIMEOUT_US = 10000; 

// ====== Battery voltage ======
static const int PIN_BATTERY = 36;
static const float R1 = 100000.0f;
static const float R2 = 33000.0f;
static const float VOLTAGE_DIVIDER = R2 / (R1 + R2);
static const float BATTERY_MIN_V = 11.1f;
static const float BATTERY_MAX_V = 12.62f;