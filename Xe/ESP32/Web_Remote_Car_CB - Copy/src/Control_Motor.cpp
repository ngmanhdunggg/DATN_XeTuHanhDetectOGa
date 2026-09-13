#include "Control_Motor.h"
#include "Config.h"

int g_lastPwm = 0;
static volatile long g_encoderCount = 0;
static portMUX_TYPE  g_encMux = portMUX_INITIALIZER_UNLOCKED;

inline void pwmWriteSafe(int ch, int val){ ledcWrite(ch, val); }

void motorDrivePWM(int pwm){
  pwm = constrain(pwm, -255, 255);
  if (abs(pwm) < PWM_DEADBAND) pwm = 0;
  if (pwm >= 0){ pwmWriteSafe(CH_RPWM, 0); pwmWriteSafe(CH_LPWM, pwm); }
  else { pwmWriteSafe(CH_RPWM, -pwm); pwmWriteSafe(CH_LPWM, 0); }
  g_lastPwm = pwm;
}

void motorBrake(){ 
  pwmWriteSafe(CH_RPWM, 255); 
  pwmWriteSafe(CH_LPWM, 255); 
  g_lastPwm = 0; 
}

void IRAM_ATTR encoderISR(){
  int b = digitalRead(PIN_ENC_B);
  portENTER_CRITICAL_ISR(&g_encMux);
  g_encoderCount += (b>0) ? 1 : -1;
  portEXIT_CRITICAL_ISR(&g_encMux);
}

long getEncoderCount() {
  long snap;
  portENTER_CRITICAL(&g_encMux);
  snap = g_encoderCount;
  portEXIT_CRITICAL(&g_encMux);
  return snap;
}

void motorHardwareBegin() {
  pinMode(PIN_REN,OUTPUT); pinMode(PIN_LEN,OUTPUT);
  digitalWrite(PIN_REN,HIGH); digitalWrite(PIN_LEN,HIGH);
  ledcSetup(CH_RPWM, PWM_FREQ, PWM_BITS); ledcAttachPin(PIN_RPWM, CH_RPWM);
  ledcSetup(CH_LPWM, PWM_FREQ, PWM_BITS); ledcAttachPin(PIN_LPWM, CH_LPWM);
  pinMode(PIN_ENC_A,INPUT_PULLUP); pinMode(PIN_ENC_B,INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_A), encoderISR, RISING);
}