/**
 * config_http.h - HTTP Polling Firmware Config
 * No MQTT broker needed — ESP32 polls backend over local WiFi.
 *
 * EDIT THESE VALUES before flashing:
 */

#ifndef CONFIG_HTTP_H
#define CONFIG_HTTP_H

// ─────────────────────────────────────────────────────────────
// WiFi — your home/lab network
// ─────────────────────────────────────────────────────────────
#define WIFI_SSID       "uday"           // ← Your WiFi name
#define WIFI_PASSWORD   ""               // ← Your WiFi password (blank if open)

// ─────────────────────────────────────────────────────────────
// Backend — your LOCAL backend IP:port
// Run: ipconfig in cmd and use the IPv4 address (e.g. 192.168.1.5)
// Make sure the backend is running: uvicorn main:app --host 0.0.0.0 --port 8000
// ─────────────────────────────────────────────────────────────
#define BACKEND_HOST    "192.168.1.5"    // ← Your PC's local IP (run ipconfig)
#define BACKEND_PORT    8000
#define JUNCTION_ID     "junction_001"

// API endpoints (do not change)
#define ENDPOINT_POLL   "/api/hardware/esp32/poll"
#define ENDPOINT_ACK    "/api/hardware/esp32/ack"
#define ENDPOINT_HB     "/api/hardware/esp32/heartbeat"

// ─────────────────────────────────────────────────────────────
// GPIO Pin Definitions — 12 LEDs, 4 directions × 3 colors
// ─────────────────────────────────────────────────────────────
#define PIN_NORTH_RED    2
#define PIN_NORTH_YELLOW 4
#define PIN_NORTH_GREEN  5

#define PIN_SOUTH_RED    12
#define PIN_SOUTH_YELLOW 13
#define PIN_SOUTH_GREEN  14

#define PIN_EAST_RED     18
#define PIN_EAST_YELLOW  19
#define PIN_EAST_GREEN   21

#define PIN_WEST_RED     22
#define PIN_WEST_YELLOW  23
#define PIN_WEST_GREEN   25

// ─────────────────────────────────────────────────────────────
// Timing
// ─────────────────────────────────────────────────────────────
#define POLL_INTERVAL_MS     1000UL   // Poll backend every 1 second
#define HEARTBEAT_INTERVAL   10000UL  // Send heartbeat every 10 seconds
#define YELLOW_DURATION_MS   3000UL   // 3s yellow before switching
#define ALL_RED_DURATION_MS  2000UL   // 2s all-red clearance
#define HTTP_TIMEOUT_MS      3000     // HTTP request timeout

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

#endif // CONFIG_HTTP_H
