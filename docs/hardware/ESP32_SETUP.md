# ESP32 Hardware Setup Guide

Refer also to [esp32/documentation/SETUP.md](../../esp32/documentation/SETUP.md) and [esp32/documentation/MQTT_PROTOCOL.md](../../esp32/documentation/MQTT_PROTOCOL.md).

## Pin Mapping (12 Physical LEDs)
| Direction | Red GPIO | Yellow GPIO | Green GPIO |
|-----------|----------|-------------|------------|
| North | GPIO 2 | GPIO 4 | GPIO 5 |
| South | GPIO 12 | GPIO 13 | GPIO 14 |
| East | GPIO 18 | GPIO 19 | GPIO 21 |
| West | GPIO 22 | GPIO 23 | GPIO 25 |

## Required Arduino Libraries
- `PubSubClient` (Nick O'Leary, v2.8.0+)
- `ArduinoJson` (Benoit Blanchon, v6.21.0+)
- ESP32 Arduino Core (`WiFi`, `WiFiClientSecure`, `ArduinoOTA`)

## Steps Before Flashing
1. Edit `esp32/firmware/config.h` with your Wi-Fi SSID/password and MQTT broker credentials.
2. Paste your MQTT broker CA certificate into `esp32/firmware/tls_certs.h`.
3. Open `esp32/firmware/main.ino` in Arduino IDE, select **ESP32 Dev Module**, and upload at 115200 baud.
4. Confirm startup LED test pattern and `signals/status` heartbeat in Serial Monitor.
