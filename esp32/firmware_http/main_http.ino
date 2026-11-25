/**
 * main_http.ino — Smart Traffic ESP32 HTTP-Polling Firmware
 * ============================================================
 * No MQTT broker required. ESP32 polls your local backend
 * over WiFi to get signal commands, then controls 12 LEDs.
 *
 * Libraries (install in Arduino IDE → Library Manager):
 *   - ArduinoJson  by Benoit Blanchon  (v6.21+)
 *   - HTTPClient   (built-in with ESP32 Arduino core)
 *   - WiFi         (built-in with ESP32 Arduino core)
 *
 * Setup:
 *   1. Edit config_http.h: set WIFI_SSID, WIFI_PASSWORD, BACKEND_HOST
 *   2. Install libraries above
 *   3. Board: "ESP32 Dev Module"
 *   4. Flash at 115200 baud
 */

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "config_http.h"

// ─────────────────────────────────────────────────────────────
// Signal State
// ─────────────────────────────────────────────────────────────
enum class Phase { RED, YELLOW, GREEN };

struct Direction {
  const char* name;
  uint8_t pinRed, pinYellow, pinGreen;
  Phase    current;
};

Direction dirs[4] = {
  {"north", PIN_NORTH_RED, PIN_NORTH_YELLOW, PIN_NORTH_GREEN, Phase::RED},
  {"south", PIN_SOUTH_RED, PIN_SOUTH_YELLOW, PIN_SOUTH_GREEN, Phase::RED},
  {"east",  PIN_EAST_RED,  PIN_EAST_YELLOW,  PIN_EAST_GREEN,  Phase::RED},
  {"west",  PIN_WEST_RED,  PIN_WEST_YELLOW,  PIN_WEST_GREEN,  Phase::RED},
};

// ─────────────────────────────────────────────────────────────
// Pending command from backend
// ─────────────────────────────────────────────────────────────
struct SignalCommand {
  int    activeDir     = -1;   // index 0-3, or -1 for all-red
  uint32_t greenMs     = 30000;
  uint32_t seq         = 0;
  bool   valid         = false;
};

SignalCommand pendingCmd;
SignalCommand activeCmd;

// Transition state machine
enum class TxState { IDLE, GREEN, GOING_YELLOW, ALL_RED };
TxState txState       = TxState::IDLE;
uint32_t txStart      = 0;
uint32_t lastPoll     = 0;
uint32_t lastHB       = 0;
uint32_t lastAckedSeq = 0;

// ─────────────────────────────────────────────────────────────
// LED Control
// ─────────────────────────────────────────────────────────────
void setLED(Direction& d, Phase p) {
  d.current = p;
  digitalWrite(d.pinRed,    p == Phase::RED    ? HIGH : LOW);
  digitalWrite(d.pinYellow, p == Phase::YELLOW ? HIGH : LOW);
  digitalWrite(d.pinGreen,  p == Phase::GREEN  ? HIGH : LOW);
}

void allRed() {
  for (auto& d : dirs) setLED(d, Phase::RED);
  DBG("[LED] All RED");
}

void applyGreen(int idx) {
  for (int i = 0; i < 4; i++) {
    setLED(dirs[i], i == idx ? Phase::GREEN : Phase::RED);
  }
  DBGf("[LED] %s GREEN, others RED\n", dirs[idx].name);
}

void applyYellow(int idx) {
  for (int i = 0; i < 4; i++) {
    setLED(dirs[i], i == idx ? Phase::YELLOW : Phase::RED);
  }
  DBGf("[LED] %s YELLOW (transitioning)\n", dirs[idx].name);
}

// Safety: prevent conflicting greens — only one green allowed
bool safetyCheck(int greenIdx) {
  int greenCount = 0;
  for (int i = 0; i < 4; i++) {
    if (dirs[i].current == Phase::GREEN) greenCount++;
  }
  return greenCount <= 1;
}

// ─────────────────────────────────────────────────────────────
// WiFi
// ─────────────────────────────────────────────────────────────
void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  DBGf("[WiFi] Connecting to %s", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    delay(500); Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    DBGf("\n[WiFi] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    DBG("\n[WiFi] Failed — will retry");
  }
}

// ─────────────────────────────────────────────────────────────
// HTTP Helpers
// ─────────────────────────────────────────────────────────────
String buildURL(const char* endpoint) {
  return String("http://") + BACKEND_HOST + ":" + BACKEND_PORT + endpoint;
}

// Poll backend for latest signal command
bool pollBackend() {
  if (WiFi.status() != WL_CONNECTED) return false;

  HTTPClient http;
  String url = buildURL(ENDPOINT_POLL);
  url += "?junction_id=" + String(JUNCTION_ID);
  http.begin(url);
  http.setTimeout(HTTP_TIMEOUT_MS);

  int code = http.GET();
  if (code != 200) {
    DBGf("[HTTP] Poll failed: %d\n", code);
    http.end();
    return false;
  }

  String body = http.getString();
  http.end();

  StaticJsonDocument<512> doc;
  if (deserializeJson(doc, body)) {
    DBG("[HTTP] JSON parse error");
    return false;
  }

  uint32_t seq = doc["sequence_id"] | 0;
  if (seq == lastAckedSeq && pendingCmd.seq == seq) return true; // no new command

  const char* dir = doc["green_direction"] | "";
  int dirIdx = -1;
  for (int i = 0; i < 4; i++) {
    if (strcmp(dirs[i].name, dir) == 0) { dirIdx = i; break; }
  }

  pendingCmd.activeDir = dirIdx;
  pendingCmd.greenMs   = (doc["duration_ms"] | 30000);
  pendingCmd.seq       = seq;
  pendingCmd.valid     = true;

  DBGf("[Poll] seq=%d dir=%s dur=%dms\n", seq, dir, pendingCmd.greenMs);
  return true;
}

// ACK back to backend
void sendAck(uint32_t seq, bool ok, const char* reason = "") {
  if (WiFi.status() != WL_CONNECTED) return;
  HTTPClient http;
  http.begin(buildURL(ENDPOINT_ACK));
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<256> doc;
  doc["junction_id"]  = JUNCTION_ID;
  doc["sequence_id"]  = seq;
  doc["ack"]          = ok;
  doc["reason"]       = reason;
  doc["rssi"]         = WiFi.RSSI();

  String body; serializeJson(doc, body);
  int code = http.POST(body);
  http.end();
  DBGf("[ACK] seq=%d ok=%d code=%d\n", seq, ok, code);
}

// Heartbeat
void sendHeartbeat() {
  if (WiFi.status() != WL_CONNECTED) return;
  HTTPClient http;
  http.begin(buildURL(ENDPOINT_HB));
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.addHeader("Content-Type", "application/json");

  // Build current state JSON
  StaticJsonDocument<512> doc;
  doc["junction_id"] = JUNCTION_ID;
  doc["rssi"]        = WiFi.RSSI();
  doc["uptime_ms"]   = millis();
  doc["free_heap"]   = ESP.getFreeHeap();

  JsonObject phases = doc.createNestedObject("phases");
  for (auto& d : dirs) {
    const char* ph = (d.current == Phase::GREEN) ? "green"
                   : (d.current == Phase::YELLOW) ? "yellow" : "red";
    phases[d.name] = ph;
  }

  String body; serializeJson(doc, body);
  int code = http.POST(body);
  http.end();
  DBGf("[HB] rssi=%d code=%d\n", WiFi.RSSI(), code);
}

// ─────────────────────────────────────────────────────────────
// Setup
// ─────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(500);
  DBG("\n[Boot] Smart Traffic ESP32 HTTP Firmware v2.0");

  // Init all LED pins
  for (auto& d : dirs) {
    pinMode(d.pinRed,    OUTPUT);
    pinMode(d.pinYellow, OUTPUT);
    pinMode(d.pinGreen,  OUTPUT);
  }
  allRed(); // Safe start state

  connectWiFi();

  // Startup blink: flash all green once to confirm wiring
  delay(500);
  for (auto& d : dirs) setLED(d, Phase::GREEN);
  DBG("[Boot] LED test: all GREEN for 1s");
  delay(1000);
  allRed();
  DBG("[Boot] LED test done. Starting poll loop.");
}

// ─────────────────────────────────────────────────────────────
// Main Loop — State Machine
// ─────────────────────────────────────────────────────────────
void loop() {
  uint32_t now = millis();

  // 1. Reconnect WiFi if needed
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
    return;
  }

  // 2. Poll backend for new command
  if (now - lastPoll >= POLL_INTERVAL_MS) {
    lastPoll = now;
    pollBackend();
  }

  // 3. Heartbeat
  if (now - lastHB >= HEARTBEAT_INTERVAL) {
    lastHB = now;
    sendHeartbeat();
  }

  // 4. Signal Transition State Machine
  switch (txState) {

    case TxState::IDLE:
      // Check for new pending command
      if (pendingCmd.valid && pendingCmd.seq != lastAckedSeq) {
        activeCmd = pendingCmd;
        lastAckedSeq = activeCmd.seq;

        if (activeCmd.activeDir >= 0) {
          applyGreen(activeCmd.activeDir);
          txState  = TxState::GREEN;
          txStart  = now;
          sendAck(activeCmd.seq, true, "executing");
          DBGf("[SM] IDLE→GREEN dir=%s dur=%dms\n",
               dirs[activeCmd.activeDir].name, activeCmd.greenMs);
        } else {
          allRed();
          sendAck(activeCmd.seq, true, "all_red");
          // stay IDLE
        }
      }
      break;

    case TxState::GREEN:
      if (now - txStart >= activeCmd.greenMs) {
        // Green time expired → go yellow
        if (activeCmd.activeDir >= 0) {
          applyYellow(activeCmd.activeDir);
        }
        txState = TxState::GOING_YELLOW;
        txStart = now;
        DBG("[SM] GREEN→YELLOW");
      }
      // Also switch early if new command arrived for different direction
      if (pendingCmd.valid && pendingCmd.seq != lastAckedSeq &&
          pendingCmd.activeDir != activeCmd.activeDir) {
        applyYellow(activeCmd.activeDir);
        txState = TxState::GOING_YELLOW;
        txStart = now;
        DBG("[SM] GREEN→YELLOW (early switch)");
      }
      break;

    case TxState::GOING_YELLOW:
      if (now - txStart >= YELLOW_DURATION_MS) {
        allRed();
        txState = TxState::ALL_RED;
        txStart = now;
        DBG("[SM] YELLOW→ALL_RED");
      }
      break;

    case TxState::ALL_RED:
      if (now - txStart >= ALL_RED_DURATION_MS) {
        txState = TxState::IDLE;
        DBG("[SM] ALL_RED→IDLE");
      }
      break;
  }
}
