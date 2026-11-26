/**
 * config.h - Configuration for Smart Traffic ESP32 Firmware
 * Junction: junction1
 *
 * IMPORTANT: Replace WiFi/MQTT credentials before flashing!
 */

#ifndef CONFIG_H
#define CONFIG_H

// ─────────────────────────────────────────────────────────────
// WiFi Configuration
// ─────────────────────────────────────────────────────────────
#define WIFI_SSID       "uday"
#define WIFI_PASSWORD   ""

// ─────────────────────────────────────────────────────────────
// MQTT Broker Configuration
// ─────────────────────────────────────────────────────────────
#define MQTT_SERVER     "your-mqtt-broker.com"
#define MQTT_PORT       8883
#define MQTT_USER       "traffic_system"
#define MQTT_PASS       "your-mqtt-password"
#define MQTT_CLIENT_ID  "esp32_junction1"
#define JUNCTION_ID     "junction1"

// ─────────────────────────────────────────────────────────────
// MQTT Topics
// ─────────────────────────────────────────────────────────────
#define TOPIC_COMMAND   "smarttraffic/junction1/signals/command"
#define TOPIC_ACK       "smarttraffic/junction1/signals/ack"
#define TOPIC_STATUS    "smarttraffic/junction1/status"
#define TOPIC_ERROR     "smarttraffic/junction1/error"

// ─────────────────────────────────────────────────────────────
// Timing (milliseconds)
// ─────────────────────────────────────────────────────────────
#define HEARTBEAT_INTERVAL      10000UL   // 10 seconds
#define WIFI_RECONNECT_INTERVAL  5000UL   // 5 seconds
#define MQTT_RECONNECT_INTERVAL  3000UL   // 3 seconds
#define DEFAULT_GREEN_DURATION  30000UL   // 30 seconds
#define YELLOW_DURATION          3000UL   // 3 seconds (fixed safety transition)
#define ALL_RED_DURATION         2000UL   // 2 seconds (fixed safety clearance)
#define MIN_GREEN_DURATION      15000UL   // 15 seconds minimum green
#define MAX_GREEN_DURATION     120000UL   // 120 seconds maximum green

// ─────────────────────────────────────────────────────────────
// MQTT Message Buffer
// ─────────────────────────────────────────────────────────────
#define MQTT_MAX_PACKET_SIZE    512
#define JSON_DOC_SIZE           512

// ─────────────────────────────────────────────────────────────
// Pin Definitions
// ─────────────────────────────────────────────────────────────

// North direction (using former East pins)
#define PIN_NORTH_RED    26
#define PIN_NORTH_YELLOW 27
#define PIN_NORTH_GREEN  32

// South direction (using former West pins)
#define PIN_SOUTH_RED    33
#define PIN_SOUTH_YELLOW 16
#define PIN_SOUTH_GREEN  17

// East direction (using former South pins)
#define PIN_EAST_RED     12
#define PIN_EAST_YELLOW  13
#define PIN_EAST_GREEN   14

// West direction (using former North pins)
#define PIN_WEST_RED     2
#define PIN_WEST_YELLOW  4
#define PIN_WEST_GREEN   5

// ─────────────────────────────────────────────────────────────
// Debug
// ─────────────────────────────────────────────────────────────
#define SERIAL_BAUD     115200
#define DEBUG_ENABLED   true

#if DEBUG_ENABLED
  #define DBG(msg)      Serial.println(msg)
  #define DBGf(fmt,...) Serial.printf(fmt, ##__VA_ARGS__)
#else
  #define DBG(msg)
  #define DBGf(fmt,...)
#endif

#endif // CONFIG_H
