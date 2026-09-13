#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <WebSocketsServer.h>
#include <ESPmDNS.h>
#include "Config.h"
#include "Control.h"
#include "WebUI.h"
#include "Sensors.h"

static WebServer server(80);
static WebSocketsServer ws(81);
static unsigned long lastWiFiCheck = 0;
const unsigned long WIFI_RECONNECT_INTERVAL = 2000;

// ===== Handlers =====
static void handleRoot() { 
    server.send(200, "text/html", WEB_PAGE); 
}

static void handleStatus() {
    char buf[160];
    controlFillStatusJSON(buf, sizeof(buf));
    server.sendHeader("Cache-Control", "no-cache, no-store, must-revalidate");
    server.sendHeader("Pragma", "no-cache");
    server.sendHeader("Expires", "0");
    server.send(200, "application/json", buf);
}

static void handleMode() {
    bool softAuto = false;
    if (server.hasArg("auto")) softAuto = (server.arg("auto").toInt() != 0);
    controlSetSoftAuto(softAuto);
    if (!softAuto) controlForceManualNeutralGate();
    server.send(200, "text/plain", softAuto ? "AUTO" : "MANUAL");
}

static void handleAuto() {
    float dc_mps = 0.0f, sv_deg = 0.0f;
    if (server.hasArg("dc")) dc_mps = atof(server.arg("dc").c_str());
    if (server.hasArg("sv")) sv_deg = atof(server.arg("sv").c_str());
    controlOnAutoSet(constrain(dc_mps, -MAX_MPS, MAX_MPS), constrain(sv_deg, -MAX_STEER_DEG, MAX_STEER_DEG));
    controlOnHeartbeat();
    server.send(200, "text/plain", "OK");
}

static void handlePing() {
    controlOnHeartbeat();
    server.send(200, "text/plain", "OK");
}

// ===== WS =====
static void handleWsMsg(uint8_t *payload, size_t len) {
    static char buf[64];
    size_t n = min(len, sizeof(buf) - 1);
    memcpy(buf, payload, n);
    buf[n] = 0;
    char *pMode = strstr(buf, "mode:");
    if (pMode) {
        bool softAuto = (atoi(pMode + 5) != 0);
        controlSetSoftAuto(softAuto);
        if (!softAuto) controlForceManualNeutralGate();
        controlOnHeartbeat();
        return; 
    }
    if (len == 2 && payload[0] == 'h' && payload[1] == 'b') {
        controlOnHeartbeat();
        return;
    }
    if (controlIsAuto()) {
        controlOnHeartbeat();
        return;
    }
    char *pdc = strstr(buf, "dc:");
    char *psv = strstr(buf, "sv:");
    float dc_mps = 0.0f, sv_deg = 0.0f;
    if (pdc) dc_mps = atof(pdc + 3);
    if (psv) {
        char *psvVal = strchr(psv, ':');
        if (psvVal) sv_deg = atof(psvVal + 1);
    }
    controlOnManualWS(constrain(dc_mps, -MAX_MPS, MAX_MPS), constrain(sv_deg, -MAX_STEER_DEG, MAX_STEER_DEG));
    controlOnHeartbeat();
}

static void onWsEvent(uint8_t num, WStype_t type, uint8_t *payload, size_t length) {
    if (type == WStype_TEXT) handleWsMsg(payload, length);
    else controlOnHeartbeat();
}

// ===== Public =====
void netBegin() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PSK);
    WiFi.setSleep(false);
    WiFi.setAutoReconnect(true);
    Serial.println("WiFi: Dang khoi tao ket noi...");
    server.on("/", handleRoot);
    server.on("/status", handleStatus);
    server.on("/mode", handleMode);
    server.on("/auto", handleAuto);
    server.on("/hb", handlePing);
    server.begin();

    ws.begin();
    ws.onEvent(onWsEvent);
}

void netLoop() {
    unsigned long now = millis();
    // --- Reconnect WiFi mỗi 2 giây nếu mất kết nối ---
    if (WiFi.status() != WL_CONNECTED) {
        if (now - lastWiFiCheck >= WIFI_RECONNECT_INTERVAL) {
            lastWiFiCheck = now;
            Serial.println("WiFi: Dang tim lai tin hieu...");
            if (WiFi.status() == WL_IDLE_STATUS || WiFi.status() == WL_DISCONNECTED) {
                WiFi.begin(WIFI_SSID, WIFI_PSK);
            }
        }
        return;
    }

    // --- Chạy server nếu đã kết nối ---
    server.handleClient();
    ws.loop();

    static unsigned long lastSample = 0;
    int rssi = WiFi.RSSI();
    bool isAuto = controlIsAuto();
    unsigned long sampleInterval = isAuto ? 150 : (rssi > -65 ? 200 : 500);
    if (now - lastSample >= sampleInterval) {
        lastSample = now;
        float rpm, setrpm, svAbs;
        int pwm; bool md;
        controlGetState(rpm, pwm, svAbs, setrpm, md);
        float batPercent = getBatteryPercent();
        float us1 = getDistanceCm(0), us2 = getDistanceCm(1), us3 = getDistanceCm(2);
        if (isinf(us1) || isnan(us1)) us1 = -1.0f;
        if (isinf(us2) || isnan(us2)) us2 = -1.0f;
        if (isinf(us3) || isnan(us3)) us3 = -1.0f;
        char msg[160];
        snprintf(msg, sizeof(msg),
             "state:sv=%.2f,dc=%.1f,rpm=%.1f,pwm=%d,md=%d,volt=%.2f,bat=%.0f,us1=%.1f,us2=%.1f,us3=%.1f,rssi=%d",
             svAbs, (fabsf(setrpm) < 2.5f) ? 0 : roundf(setrpm), 
             roundf(rpm), pwm, md ? 1 : 0, 
             getBatteryVoltage(), batPercent, us1, us2, us3, rssi);
        if (ws.connectedClients() > 0) {
            ws.broadcastTXT(msg);
        }
    }
}