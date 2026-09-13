#include "Control.h"
#include "Config.h"
#include "Sensors.h"
#include "Control_Safety.h"
#include "Control_Parser.h"
#include "Control_Motor.h"
#include <ESP32Servo.h>
#include <WiFi.h>
#include <math.h>

static Servo g_servo;
static float g_curRpm = 0.0f;
static float g_setpoint_rpm = 0.0f;        
static float g_rampSet_rpm  = 0.0f;
static float g_integral = 0.0f, g_lastErr = 0.0f;
static float g_speedBuf[FILTER_SIZE];
static int    g_fi = 0;
static float g_servoTargetAbs = SERVO_CENTER;  
static float g_servoPosAbs    = SERVO_CENTER;  
static bool  g_softAuto = false;
static bool  g_autoMode = false;
static bool  g_lastAuto = false;
static volatile bool g_manualNeedsNeutral = false;
static unsigned long g_lastRxMs = 0;
static bool  g_linkLost = false;
static unsigned long g_lastTick = 0;
static long g_lastEnc = 0;
static float g_dt = LOOP_DT_S;
static bool g_isReversingLock = false; 
// auto-hold
static bool  autoHoldActive = false, holdArming = false, sp0Counting = false;
static unsigned long holdArmStart = 0, lastHoldCheck = 0, sp0Start = 0;
static int   holdStickPWM = 0;
// Ramps
static float rampUpStep   = 10.0f; 
static float rampDownStep = 5.0f;

static float filterRPM(float v) {
  g_speedBuf[g_fi] = v;
  g_fi = (g_fi + 1) % FILTER_SIZE;
  float s = 0; for (int i = 0; i < FILTER_SIZE; i++) s += g_speedBuf[i];
  return s / FILTER_SIZE;
}

static void checkLinkAndModeTransitions(unsigned long now) {
  bool wifiConnected = (WiFi.status() == WL_CONNECTED);
  bool rssiOk = isWifiStrongEnough();
  bool hasGoodLink = wifiConnected && rssiOk;
  bool isTimeout = (now - g_lastRxMs > TIMEOUT_MS);
  bool linkBad = (!hasGoodLink || isTimeout);
  if (linkBad) {
    if (!g_linkLost) {
      g_linkLost = true;
      g_integral = 0; g_lastErr = 0;
      g_setpoint_rpm = 0; g_rampSet_rpm = 0;
      sp0Counting = true; sp0Start = now;
      g_servoTargetAbs = SERVO_CENTER;
    }
  } else {
    if (g_linkLost) g_linkLost = false;
  }
  if (g_autoMode != g_lastAuto) {
    g_integral = 0; g_lastErr = 0;
    if (!g_autoMode) { 
      g_setpoint_rpm = 0; g_rampSet_rpm = 0; g_isReversingLock = false;
      autoHoldActive = false; holdArming = false; motorBrake();
      g_servo.write(SERVO_CENTER); g_manualNeedsNeutral = true;
    }
    g_lastAuto = g_autoMode;
  }
}

static void updateServoRamp() {
  float maxStep = SERVO_RATE_DPS * g_dt;
  float diff = g_servoTargetAbs - g_servoPosAbs;
  if (diff > maxStep) g_servoPosAbs += maxStep;
  else if (diff < -maxStep) g_servoPosAbs -= maxStep;
  else g_servoPosAbs = g_servoTargetAbs;
  g_servoPosAbs = constrain(g_servoPosAbs, SERVO_MIN, SERVO_MAX);
  g_servo.write(g_servoPosAbs);
}

static void calculateCurrentRPM() {
  long encSnap = getEncoderCount();
  long delta = encSnap - g_lastEnc; g_lastEnc = encSnap;
  float rpm = -(float)delta / (float)ENCODER_COUNTS_PER_REV / g_dt * 60.0f;
  g_curRpm = filterRPM(rpm);
}

static float processReverseLockAndSafety() {
  float stopThreshold = 20.0f; 
  if (!g_isReversingLock) {
    if ((g_setpoint_rpm > 2.0f && g_curRpm < -stopThreshold) || 
        (g_setpoint_rpm < -2.0f && g_curRpm > stopThreshold)) {
      g_isReversingLock = true; 
    }
  }
  float effectiveSetpoint = g_setpoint_rpm; 
  if (g_isReversingLock) {
    effectiveSetpoint = 0.0f; 
    if (fabsf(g_curRpm) < 2.0f) { 
      g_isReversingLock = false; 
      g_integral = 0; g_lastErr = 0; 
    }
  }
  float desired_mps = effectiveSetpoint * RPM2MPS;
  float safe_mps = applySafetyLimit(desired_mps);
  return safe_mps * MPS2RPM;
}

static void updateSetpointRamp(float effectiveSetpoint) {
  if (g_linkLost) {
    float diff = 0.0f - g_rampSet_rpm;
    if (diff > 0) g_rampSet_rpm += min(diff, rampDownStep);
    else          g_rampSet_rpm += max(diff, -rampDownStep);
  } else {
    if (fabsf(effectiveSetpoint) > fabsf(g_rampSet_rpm)) {
      float diff = effectiveSetpoint - g_rampSet_rpm;
      if (diff > 0) g_rampSet_rpm += min(diff, rampUpStep);
      else          g_rampSet_rpm += max(diff, -rampUpStep);
    } else {
      g_rampSet_rpm = effectiveSetpoint;
    }
  }
  if (fabsf(g_rampSet_rpm) < 2.5f && fabsf(effectiveSetpoint) < 2.5f) g_rampSet_rpm = 0;
}

static void handlePIDControl(float effectiveSetpoint) {
  autoHoldActive = false; holdArming = false; holdStickPWM = 0; sp0Counting = false;
  static float lastSet = 0;
  if ((effectiveSetpoint > 0 && lastSet <= 0) || (effectiveSetpoint < 0 && lastSet >= 0)) {
    g_integral = 0; g_lastErr = 0;
  }
  lastSet = effectiveSetpoint;
  float err = g_rampSet_rpm - g_curRpm;
  g_integral += err * g_dt;
  if (Ki > 0) {
    float I_MAX = 255.0f / Ki;
    if (g_integral > I_MAX) g_integral = I_MAX;
    if (g_integral < -I_MAX) g_integral = -I_MAX;
  }
  float deriv = (err - g_lastErr) / g_dt;
  float out = Kp * err + Ki * g_integral + Kd * deriv;
  g_lastErr = err;
  motorDrivePWM(constrain((int)lroundf(out), -255, 255));
}

static void handleAutoHold(unsigned long now) {
  if (!sp0Counting) { sp0Counting = true; sp0Start = now; }
  else {
    if ((now - sp0Start) >= HOLD_SP0_MS && !autoHoldActive) {
      autoHoldActive = true; holdArming = false; lastHoldCheck = now;
      int desiredSign = (g_curRpm > 0) ? -1 : +1;
      holdStickPWM = constrain(desiredSign * HOLD_INIT_PWM, -HOLD_MAX_PWM, HOLD_MAX_PWM);
    }
  }

  if (!autoHoldActive) {
    if (!holdArming) {
      if (fabsf(g_curRpm) < HOLD_RPM_TH) { holdArming = true; holdArmStart = now; }
      motorDrivePWM(0);
    } else {
      if (fabsf(g_curRpm) >= HOLD_RPM_TH) { holdArming = false; motorDrivePWM(0); }
      else if (now - holdArmStart >= HOLD_ARM_MS) { autoHoldActive = true; lastHoldCheck = now; }
      else motorDrivePWM(0);
    }
  } else {
    int pwmApply = (abs(holdStickPWM) < HOLD_MIN_PWM) ? 0 : holdStickPWM;
    motorDrivePWM(pwmApply);
    if (now - lastHoldCheck >= HOLD_PERIOD_MS) {
      lastHoldCheck = now;
      if (fabsf(g_curRpm) >= HOLD_RPM_TH) {
        int desiredSign = (g_curRpm > 0) ? -1 : +1;
        if (holdStickPWM == 0 || (holdStickPWM * desiredSign < 0)) holdStickPWM = desiredSign * HOLD_INIT_PWM;
        else holdStickPWM += desiredSign * HOLD_ADJ_STEP;
        holdStickPWM = constrain(holdStickPWM, -HOLD_MAX_PWM, HOLD_MAX_PWM);
      }
    }
  }
}

static void sendTelemetry(unsigned long now) {
  static unsigned long lastTeleUART = 0;
  if (now - lastTeleUART >= 100) {
      lastTeleUART = now;      
      float real_mps = g_curRpm * RPM2MPS;
      float real_steer = (g_servoPosAbs - SERVO_CENTER) * SERVO_TO_STEER;      
      float target_mps = g_rampSet_rpm * RPM2MPS;
      float original_mps = g_setpoint_rpm * RPM2MPS;
      float target_steer = (g_servoTargetAbs - SERVO_CENTER) * SERVO_TO_STEER;
      
      float batPct = getBatteryPercent();
      float distPothole = getDistanceCm(0);
      float distFront = getDistanceCm(1);
      float distRear = getDistanceCm(2);
      int mode = g_autoMode ? 1 : 0;
      RPI_SERIAL.printf("FB:S=%.2f|A=%.2f|B=%.0f|P=%.1f|F=%.1f|R=%.1f|M=%d\n", 
                        real_mps, real_steer, batPct, distPothole, distFront, distRear, mode);
      
      Serial.printf("FB:TocDo=%.2f|GocLai=%.2f|RampTocDo=%.2f|Setpoint=%.2f|SetpointGocLai=%.2f|Pin=%.0f|OGa=%.1f|CBTruoc=%.1f|CBsau=%.1f|CheDo=%d\n", 
                    real_mps, real_steer, target_mps, original_mps, target_steer,
                    batPct, distPothole, distFront, distRear, mode);
  }
}

void controlGetState(float& rpm, int& pwm, float& servoAbsDeg, float& set_rpm, bool& isAuto) {
  rpm         = g_curRpm;
  pwm         = g_lastPwm;
  servoAbsDeg = g_servoPosAbs;
  set_rpm     = g_rampSet_rpm;
  isAuto      = g_autoMode;
}

void controlFillStatusJSON(char* buf, size_t len) {
  snprintf(buf, len,
    "{\"rpm\":%.2f,\"pwm\":%d,\"sv\":%.1f,\"dc\":%.0f,\"md\":%d}",
    g_curRpm, g_lastPwm, g_servoPosAbs,
    (fabsf(g_rampSet_rpm) < 2.5f) ? 0 : roundf(g_rampSet_rpm),
    g_autoMode ? 1 : 0
  );
}

void controlSetSoftAuto(bool on) { g_softAuto = on; }
bool controlIsAuto() { return g_autoMode; }
void controlForceManualNeutralGate() { g_manualNeedsNeutral = true; }
void controlOnHeartbeat() { g_lastRxMs = millis(); }

void controlOnAutoSet(float dc_mps, float steer_deg) {
  if (g_linkLost) return;
  if (!isWifiStrongEnough()) return;
  dc_mps    = constrain(dc_mps, -MAX_MPS, MAX_MPS);
  steer_deg = constrain(steer_deg, -MAX_STEER_DEG, MAX_STEER_DEG);
  float dc_rpm = (fabsf(dc_mps) < DEAD_MPS) ? 0.0f : (dc_mps * MPS2RPM);
  float servoAbs = SERVO_CENTER + steer_deg * STEER_TO_SERVO;
  servoAbs = constrain(servoAbs, SERVO_MIN, SERVO_MAX);
  static portMUX_TYPE cmdMux = portMUX_INITIALIZER_UNLOCKED;
  portENTER_CRITICAL(&cmdMux);
  g_setpoint_rpm   = dc_rpm;
  g_servoTargetAbs = servoAbs;
  portEXIT_CRITICAL(&cmdMux);
}

void controlOnManualWS(float dc_mps, float steer_deg) {
  if (g_linkLost) return;
  if (g_autoMode) { g_lastRxMs = millis(); return; }
  if (!isWifiStrongEnough()) { g_lastRxMs = millis(); return; }
  dc_mps    = constrain(dc_mps, -MAX_MPS, MAX_MPS);
  steer_deg = constrain(steer_deg, -MAX_STEER_DEG, MAX_STEER_DEG);
  float dc_rpm = (fabsf(dc_mps) < DEAD_MPS) ? 0.0f : (dc_mps * MPS2RPM);
  float servoAbs = SERVO_CENTER + steer_deg * STEER_TO_SERVO;
  servoAbs = constrain(servoAbs, SERVO_MIN, SERVO_MAX);
  if (g_manualNeedsNeutral) {
    bool dcNeutral = fabsf(dc_mps) <= DEAD_MPS;
    bool svNeutral = fabsf(steer_deg) <= DEAD_SERVO_DEG;
    g_lastRxMs = millis();
    if (!(dcNeutral && svNeutral)) return;
    g_manualNeedsNeutral = false;
    dc_rpm = 0; servoAbs = SERVO_CENTER;
  }
  static portMUX_TYPE cmdMux = portMUX_INITIALIZER_UNLOCKED;
  portENTER_CRITICAL(&cmdMux);
  g_setpoint_rpm  = dc_rpm;
  g_servoTargetAbs = servoAbs;
  g_lastRxMs      = millis();
  portEXIT_CRITICAL(&cmdMux);
}

bool controlIsLinkLost() {
    return g_linkLost;
}

void controlBegin() {
  motorHardwareBegin();
  g_servo.attach(PIN_SERVO);
  g_servoPosAbs = SERVO_CENTER;
  g_servo.write(g_servoPosAbs);
  for (int i = 0; i < FILTER_SIZE; i++) g_speedBuf[i] = 0;
  g_lastTick = millis(); g_lastRxMs = millis();
  motorBrake();
  RPI_SERIAL.begin(UART_BAUD, SERIAL_8N1, PIN_RX1, PIN_TX1);
}

void controlLoop50ms() {
  g_autoMode = g_softAuto;
  unsigned long now = millis();
  checkLinkAndModeTransitions(now);
  if (g_autoMode) {
    handleSerialCommands();
  }
  updateServoRamp();
  calculateCurrentRPM();
  float effectiveSetpoint = processReverseLockAndSafety();
  updateSetpointRamp(effectiveSetpoint);
  if (fabsf(effectiveSetpoint) >= 2.5f) {
    handlePIDControl(effectiveSetpoint);
  } else {
    handleAutoHold(now);
  }
  sendTelemetry(now);
}