/**
 * main.ino - Smart Traffic Management System - ESP32 Firmware
 * Junction: junction1
 *
 * Hardware:
 *   - ESP32 Development Board
 *   - 12 LEDs: 4 directions × 3 colors (Red/Yellow/Green)
 *   - 330Ω resistors per LED
 *
 * Libraries Required (install via Arduino Library Manager):
 *   - PubSubClient  by Nick O'Leary  (v2.8.0+)
 *   - ArduinoJson   by Benoit Blanchon (v6.21.0+)
 *   - WiFi          (built-in with ESP32 Arduino core)
 *   - WiFiClientSecure (built-in with ESP32 Arduino core)
 *   - ArduinoOTA    (built-in with ESP32 Arduino core)
 *
 * Safety: Signal safety is enforced BOTH in firmware AND backend.
 *         The firmware will NEVER allow conflicting greens regardless of
 *         what command it receives.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <ArduinoOTA.h>

#include "config.h"
#include "signal_safety.h"
#include "tls_certs.h"

// ─────────────────────────────────────────────────────────────
// Global State
// ─────────────────────────────────────────────────────────────

WiFiClientSecure tlsClient;
PubSubClient     mqttClient(tlsClient);

// Current signal states for all 4 directions
DirectionState currentState[4] = {
    {SignalPhase::RED, 0},  // NORTH
    {SignalPhase::RED, 0},  // SOUTH
    {SignalPhase::RED, 0},  // EAST
    {SignalPhase::RED, 0},  // WEST
};

// Transition state machine
enum class TransitionState {
    IDLE,
    EXECUTING_GREEN,
    TRANSITIONING_TO_YELLOW,
    ALL_RED_CLEARANCE,
    APPLYING_NEW_PHASE
};

TransitionState txState = TransitionState::IDLE;
SignalCommand   pendingCommand;
bool            hasPendingCommand = false;
uint32_t        txStartTime       = 0;
uint32_t        lastHeartbeat     = 0;
uint32_t        lastWifiAttempt   = 0;
uint32_t        lastMqttAttempt   = 0;
uint32_t        greenStartTime    = 0;
uint32_t        greenDuration     = 0;

// LED pin lookup table: [direction][color] → GPIO
// color: 0=RED, 1=YELLOW, 2=GREEN
const uint8_t LED_PINS[4][3] = {
    {PIN_NORTH_RED, PIN_NORTH_YELLOW, PIN_NORTH_GREEN},  // NORTH
    {PIN_SOUTH_RED, PIN_SOUTH_YELLOW, PIN_SOUTH_GREEN},  // SOUTH
    {PIN_EAST_RED,  PIN_EAST_YELLOW,  PIN_EAST_GREEN},   // EAST
    {PIN_WEST_RED,  PIN_WEST_YELLOW,  PIN_WEST_GREEN},   // WEST
};

const char* DIRECTION_NAMES[4] = {"north", "south", "east", "west"};

// ─────────────────────────────────────────────────────────────
// LED Control Functions
// ─────────────────────────────────────────────────────────────

void initAllPins() {
    for (int d = 0; d < 4; d++) {
        for (int c = 0; c < 3; c++) {
            pinMode(LED_PINS[d][c], OUTPUT);
            digitalWrite(LED_PINS[d][c], LOW);
        }
    }
    DBG("[LED] All pins initialized LOW");
}

/**
 * Set the LED for a specific direction to a phase.
 * Automatically turns off the other two colors.
 */
void setDirectionLED(int dirIndex, SignalPhase phase) {
    // Turn all off first
    for (int c = 0; c < 3; c++) {
        digitalWrite(LED_PINS[dirIndex][c], LOW);
    }
    // Turn on the correct color
    switch (phase) {
        case SignalPhase::RED:    digitalWrite(LED_PINS[dirIndex][0], HIGH); break;
        case SignalPhase::YELLOW: digitalWrite(LED_PINS[dirIndex][1], HIGH); break;
        case SignalPhase::GREEN:  digitalWrite(LED_PINS[dirIndex][2], HIGH); break;
        default: break;  // UNKNOWN → all off (failsafe)
    }
}

/**
 * Apply a full signal state to all 4 directions simultaneously.
 */
void applySignalState(SignalPhase north, SignalPhase south, SignalPhase east, SignalPhase west) {
    setDirectionLED(0, north);
    setDirectionLED(1, south);
    setDirectionLED(2, east);
    setDirectionLED(3, west);

    currentState[0].phase = north;
    currentState[1].phase = south;
    currentState[2].phase = east;
    currentState[3].phase = west;

    DBGf("[LED] Applied: N=%s S=%s E=%s W=%s\n",
         phaseToString(north), phaseToString(south),
         phaseToString(east),  phaseToString(west));
}

/**
 * Set ALL directions to RED (emergency/all-clear state).
 */
void setAllRed() {
    applySignalState(SignalPhase::RED, SignalPhase::RED,
                     SignalPhase::RED, SignalPhase::RED);
    DBG("[LED] ALL RED applied");
}

/**
 * Set ALL directions to YELLOW (warning before ALL_RED clearance).
 */
void setAllYellow() {
    applySignalState(SignalPhase::YELLOW, SignalPhase::YELLOW,
                     SignalPhase::YELLOW, SignalPhase::YELLOW);
    DBG("[LED] ALL YELLOW applied");
}

/**
 * Startup LED test pattern: cycle through all LEDs in sequence.
 */
void ledStartupTest() {
    DBG("[LED] Running startup LED test...");
    // Light all RED
    for (int d = 0; d < 4; d++) setDirectionLED(d, SignalPhase::RED);
    delay(500);
    // Light all YELLOW
    for (int d = 0; d < 4; d++) setDirectionLED(d, SignalPhase::YELLOW);
    delay(500);
    // Light all GREEN
    for (int d = 0; d < 4; d++) setDirectionLED(d, SignalPhase::GREEN);
    delay(500);
    // Sequential flash each direction
    for (int d = 0; d < 4; d++) {
        for (int dd = 0; dd < 4; dd++) setDirectionLED(dd, SignalPhase::RED);
        setDirectionLED(d, SignalPhase::GREEN);
        delay(300);
    }
    // Return to ALL RED (safe default)
    setAllRed();
    DBG("[LED] Startup test complete. All RED.");
}

/**
 * Error blink pattern - blinks all LEDs RED rapidly to indicate firmware error.
 */
void errorBlinkPattern(int blinks = 5) {
    for (int i = 0; i < blinks; i++) {
        for (int d = 0; d < 4; d++) {
            digitalWrite(LED_PINS[d][0], HIGH);  // RED on
            for (int c = 1; c < 3; c++) digitalWrite(LED_PINS[d][c], LOW);
        }
        delay(150);
        for (int d = 0; d < 4; d++) {
            for (int c = 0; c < 3; c++) digitalWrite(LED_PINS[d][c], LOW);
        }
        delay(150);
    }
}

// ─────────────────────────────────────────────────────────────
// WiFi Functions
// ─────────────────────────────────────────────────────────────

void connectWiFi() {
    if (WiFi.status() == WL_CONNECTED) return;

    uint32_t now = millis();
    if (now - lastWifiAttempt < WIFI_RECONNECT_INTERVAL) return;
    lastWifiAttempt = now;

    DBGf("[WiFi] Connecting to: %s\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    uint32_t startTime = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - startTime) < 10000) {
        delay(500);
        DBG(".");
    }

    if (WiFi.status() == WL_CONNECTED) {
        DBGf("\n[WiFi] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
        DBGf("[WiFi] RSSI: %d dBm\n", WiFi.RSSI());
    } else {
        DBG("\n[WiFi] Connection failed. Will retry...");
        errorBlinkPattern(2);
    }
}

// ─────────────────────────────────────────────────────────────
// MQTT Publish Helpers
// ─────────────────────────────────────────────────────────────

void publishAck(uint32_t sequence_id, bool success, const char* error_msg = nullptr) {
    StaticJsonDocument<JSON_DOC_SIZE> doc;
    doc["ack"]         = success;
    doc["sequence_id"] = sequence_id;
    doc["executed_at"] = millis();
    doc["junction_id"] = JUNCTION_ID;

    JsonObject state = doc.createNestedObject("current_state");
    for (int d = 0; d < 4; d++) {
        JsonObject dir = state.createNestedObject(DIRECTION_NAMES[d]);
        dir["phase"] = phaseToString(currentState[d].phase);
    }

    if (!success && error_msg) {
        doc["error"] = error_msg;
    }

    char buffer[JSON_DOC_SIZE];
    size_t len = serializeJson(doc, buffer);
    mqttClient.publish(TOPIC_ACK, buffer, len);
    DBGf("[MQTT] Published ACK for seq_id=%lu success=%s\n",
         (unsigned long)sequence_id, success ? "true" : "false");
}

void publishHeartbeat() {
    StaticJsonDocument<JSON_DOC_SIZE> doc;
    doc["junction_id"] = JUNCTION_ID;
    doc["uptime_ms"]   = millis();
    doc["wifi_rssi"]   = WiFi.RSSI();
    doc["heap_free"]   = ESP.getFreeHeap();
    doc["state"]       = "online";

    JsonObject signals = doc.createNestedObject("signals");
    for (int d = 0; d < 4; d++) {
        JsonObject dir = signals.createNestedObject(DIRECTION_NAMES[d]);
        dir["phase"] = phaseToString(currentState[d].phase);
    }

    char buffer[JSON_DOC_SIZE];
    size_t len = serializeJson(doc, buffer);
    mqttClient.publish(TOPIC_STATUS, buffer, len);
    DBG("[MQTT] Heartbeat published");
}

void publishError(const char* error_msg) {
    StaticJsonDocument<256> doc;
    doc["junction_id"] = JUNCTION_ID;
    doc["error"]       = error_msg;
    doc["uptime_ms"]   = millis();

    char buffer[256];
    size_t len = serializeJson(doc, buffer);
    mqttClient.publish(TOPIC_ERROR, buffer, len);
    DBGf("[MQTT] Error published: %s\n", error_msg);
}

// ─────────────────────────────────────────────────────────────
// MQTT Command Handler
// ─────────────────────────────────────────────────────────────

void handleCommandMessage(byte* payload, unsigned int length) {
    // Parse JSON
    StaticJsonDocument<JSON_DOC_SIZE> doc;
    DeserializationError err = deserializeJson(doc, payload, length);

    if (err) {
        DBGf("[MQTT] JSON parse error: %s\n", err.c_str());
        publishError("JSON parse failed");
        errorBlinkPattern(3);
        return;
    }

    // Check command type
    const char* cmd = doc["cmd"] | "";
    if (strcmp(cmd, "set_phase") != 0) {
        DBGf("[MQTT] Unknown command: %s\n", cmd);
        publishError("Unknown command type");
        return;
    }

    uint32_t sequence_id = doc["sequence_id"] | 0;
    DBGf("[MQTT] Received set_phase command seq_id=%lu\n", (unsigned long)sequence_id);

    // Parse signal states for each direction
    SignalCommand command;
    command.sequence_id = sequence_id;

    auto parseDir = [&](const char* dirName, DirectionState& state) -> bool {
        JsonObject dirObj = doc["signals"][dirName];
        if (dirObj.isNull()) {
            DBGf("[MQTT] Missing direction: %s\n", dirName);
            return false;
        }
        const char* phaseStr = dirObj["phase"] | "RED";
        uint32_t durationSec = dirObj["duration"] | 30;  // seconds from backend
        state.phase = stringToPhase(phaseStr);
        state.duration_ms = durationSec * 1000UL;        // convert to ms
        if (state.phase == SignalPhase::UNKNOWN) {
            DBGf("[MQTT] Unknown phase '%s' for %s, defaulting to RED\n", phaseStr, dirName);
            state.phase = SignalPhase::RED;
        }
        return true;
    };

    if (!parseDir("north", command.north) ||
        !parseDir("south", command.south) ||
        !parseDir("east",  command.east)  ||
        !parseDir("west",  command.west)) {
        publishAck(sequence_id, false, "Invalid signal command format");
        return;
    }

    // ── FIRMWARE SAFETY VALIDATION (independent of backend) ──
    ValidationResult validation = validateSignalCommand(command);
    if (!validation.valid) {
        DBGf("[SAFETY] REJECTED command seq_id=%lu: %s\n",
             (unsigned long)sequence_id, validation.reason);
        publishAck(sequence_id, false, validation.reason);
        publishError(validation.reason);
        errorBlinkPattern(5);  // loud error indication
        return;
    }

    // Queue the command for execution by state machine
    pendingCommand    = command;
    hasPendingCommand = true;
    DBGf("[MQTT] Command seq_id=%lu queued for execution\n", (unsigned long)sequence_id);
}

// ─────────────────────────────────────────────────────────────
// MQTT Callback
// ─────────────────────────────────────────────────────────────

void mqttCallback(char* topic, byte* payload, unsigned int length) {
    DBGf("[MQTT] Message on topic: %s (%u bytes)\n", topic, length);

    if (strcmp(topic, TOPIC_COMMAND) == 0) {
        handleCommandMessage(payload, length);
    } else {
        DBGf("[MQTT] Unhandled topic: %s\n", topic);
    }
}

// ─────────────────────────────────────────────────────────────
// MQTT Connection
// ─────────────────────────────────────────────────────────────

void connectMQTT() {
    if (mqttClient.connected()) return;
    if (WiFi.status() != WL_CONNECTED) return;

    uint32_t now = millis();
    if (now - lastMqttAttempt < MQTT_RECONNECT_INTERVAL) return;
    lastMqttAttempt = now;

    DBGf("[MQTT] Connecting to %s:%d as %s\n", MQTT_SERVER, MQTT_PORT, MQTT_CLIENT_ID);

    bool connected = mqttClient.connect(
        MQTT_CLIENT_ID,
        MQTT_USER,
        MQTT_PASS,
        TOPIC_STATUS,              // LWT topic
        1,                         // LWT QoS
        true,                      // LWT retain
        "{\"state\":\"offline\"}"  // LWT message
    );

    if (connected) {
        DBG("[MQTT] Connected!");
        mqttClient.subscribe(TOPIC_COMMAND, 1);  // QoS 1
        DBGf("[MQTT] Subscribed to: %s\n", TOPIC_COMMAND);
        // Publish online status
        publishHeartbeat();
    } else {
        DBGf("[MQTT] Connection failed, state=%d. Retrying...\n", mqttClient.state());
        errorBlinkPattern(2);
    }
}

// ─────────────────────────────────────────────────────────────
// Signal State Machine
// ─────────────────────────────────────────────────────────────

/**
 * Execute pending command through the safety transition sequence:
 *   Current GREEN → YELLOW (3s) → ALL_RED (2s) → New GREEN
 *
 * This runs non-blocking via millis() timers.
 */
void runSignalStateMachine() {
    uint32_t now = millis();

    switch (txState) {
        case TransitionState::IDLE: {
            if (!hasPendingCommand) return;

            // Start transition: first go to YELLOW for currently-green directions
            bool anyGreen = false;
            for (int d = 0; d < 4; d++) {
                if (currentState[d].phase == SignalPhase::GREEN ||
                    currentState[d].phase == SignalPhase::YELLOW) {
                    anyGreen = true;
                    break;
                }
            }

            if (anyGreen) {
                // Transition current greens to yellow
                for (int d = 0; d < 4; d++) {
                    if (currentState[d].phase == SignalPhase::GREEN) {
                        setDirectionLED(d, SignalPhase::YELLOW);
                        currentState[d].phase = SignalPhase::YELLOW;
                    }
                }
                txState    = TransitionState::TRANSITIONING_TO_YELLOW;
                txStartTime = now;
                DBG("[STATE] Transitioning: GREEN → YELLOW");
            } else {
                // Already all red, go directly to new phase
                txState    = TransitionState::ALL_RED_CLEARANCE;
                txStartTime = now;
                DBG("[STATE] Skipping yellow (already red), ALL_RED clearance");
            }
            break;
        }

        case TransitionState::TRANSITIONING_TO_YELLOW: {
            if (now - txStartTime >= YELLOW_DURATION) {
                // Yellow time expired → go to ALL_RED
                setAllRed();
                txState    = TransitionState::ALL_RED_CLEARANCE;
                txStartTime = now;
                DBG("[STATE] YELLOW → ALL_RED clearance");
            }
            break;
        }

        case TransitionState::ALL_RED_CLEARANCE: {
            if (now - txStartTime >= ALL_RED_DURATION) {
                // ALL_RED clearance done → apply new command
                txState = TransitionState::APPLYING_NEW_PHASE;
            }
            break;
        }

        case TransitionState::APPLYING_NEW_PHASE: {
            // Apply the validated pending command
            applySignalState(
                pendingCommand.north.phase,
                pendingCommand.south.phase,
                pendingCommand.east.phase,
                pendingCommand.west.phase
            );

            // Store durations
            currentState[0].duration_ms = pendingCommand.north.duration_ms;
            currentState[1].duration_ms = pendingCommand.south.duration_ms;
            currentState[2].duration_ms = pendingCommand.east.duration_ms;
            currentState[3].duration_ms = pendingCommand.west.duration_ms;

            // Find max green duration for this phase
            greenDuration  = 0;
            for (int d = 0; d < 4; d++) {
                if (currentState[d].phase == SignalPhase::GREEN) {
                    if (currentState[d].duration_ms > greenDuration)
                        greenDuration = currentState[d].duration_ms;
                }
            }
            greenStartTime = now;

            // Send ACK
            publishAck(pendingCommand.sequence_id, true);
            hasPendingCommand = false;

            txState = TransitionState::EXECUTING_GREEN;
            DBGf("[STATE] New phase applied. Green for %lu ms\n", (unsigned long)greenDuration);
            break;
        }

        case TransitionState::EXECUTING_GREEN: {
            // Auto-expire: if no new command arrives, start flashing yellow then red
            if (greenDuration > 0 && (now - greenStartTime) >= greenDuration) {
                DBG("[STATE] Green duration expired, auto-transitioning to ALL_RED");
                // Auto transition to all red
                for (int d = 0; d < 4; d++) {
                    if (currentState[d].phase == SignalPhase::GREEN) {
                        setDirectionLED(d, SignalPhase::YELLOW);
                        currentState[d].phase = SignalPhase::YELLOW;
                    }
                }
                txState    = TransitionState::TRANSITIONING_TO_YELLOW;
                txStartTime = now;
                greenDuration = 0;  // prevent repeat
            }

            // Check for new pending command → start transition
            if (hasPendingCommand) {
                txState = TransitionState::IDLE;
            }
            break;
        }
    }
}

// ─────────────────────────────────────────────────────────────
// OTA Setup
// ─────────────────────────────────────────────────────────────

void setupOTA() {
    ArduinoOTA.setHostname(MQTT_CLIENT_ID);
    ArduinoOTA.setPassword("ota_password_change_me");

    ArduinoOTA.onStart([]() {
        DBG("[OTA] Starting OTA update...");
        setAllRed();  // Safe state during OTA
    });
    ArduinoOTA.onEnd([]() {
        DBG("[OTA] OTA complete! Rebooting...");
    });
    ArduinoOTA.onError([](ota_error_t error) {
        DBGf("[OTA] Error: %u\n", error);
        errorBlinkPattern(10);
    });
    ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
        DBGf("[OTA] Progress: %u%%\n", (progress / (total / 100)));
    });

    ArduinoOTA.begin();
    DBG("[OTA] OTA ready");
}

// ─────────────────────────────────────────────────────────────
// Setup
// ─────────────────────────────────────────────────────────────

void setup() {
    Serial.begin(SERIAL_BAUD);
    delay(1000);  // Allow serial to stabilize
    DBG("\n========================================");
    DBG(" Smart Traffic ESP32 Firmware v1.0.0");
    DBGf(" Junction: %s\n", JUNCTION_ID);
    DBG("========================================");

    // Initialize all LED pins
    initAllPins();

    // Run startup LED test
    ledStartupTest();

    // Connect to WiFi
    DBG("[Setup] Connecting to WiFi...");
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    uint32_t wifiStart = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - wifiStart) < 15000) {
        delay(500);
        DBG(".");
    }
    if (WiFi.status() == WL_CONNECTED) {
        DBGf("\n[Setup] WiFi OK. IP: %s\n", WiFi.localIP().toString().c_str());
    } else {
        DBG("\n[Setup] WiFi FAILED - will retry in loop");
        errorBlinkPattern(5);
    }

    // Configure TLS
    // For self-signed certs, use setInsecure() OR load the CA cert
    // Option A: Load CA cert (recommended for production)
    tlsClient.setCACert(ROOT_CA_CERT);
    // Option B: Skip cert verification (development only - INSECURE)
    // tlsClient.setInsecure();

    // For mTLS (mutual TLS):
    // tlsClient.setCertificate(CLIENT_CERT);
    // tlsClient.setPrivateKey(CLIENT_KEY);

    // Configure MQTT
    mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
    mqttClient.setCallback(mqttCallback);
    mqttClient.setBufferSize(MQTT_MAX_PACKET_SIZE);
    mqttClient.setKeepAlive(60);

    // Setup OTA
    setupOTA();

    // Initial MQTT connection
    connectMQTT();

    DBG("[Setup] Setup complete. Entering main loop.");
}

// ─────────────────────────────────────────────────────────────
// Loop
// ─────────────────────────────────────────────────────────────

void loop() {
    // 1. Maintain WiFi
    if (WiFi.status() != WL_CONNECTED) {
        connectWiFi();
        return;  // Don't process MQTT without WiFi
    }

    // 2. Maintain MQTT
    if (!mqttClient.connected()) {
        connectMQTT();
        return;
    }

    // 3. Process MQTT messages
    mqttClient.loop();

    // 4. Run signal state machine (non-blocking)
    runSignalStateMachine();

    // 5. Send periodic heartbeat
    uint32_t now = millis();
    if (now - lastHeartbeat >= HEARTBEAT_INTERVAL) {
        lastHeartbeat = now;
        publishHeartbeat();
    }

    // 6. Handle OTA
    ArduinoOTA.handle();
}
