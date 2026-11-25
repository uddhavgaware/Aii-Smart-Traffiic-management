# ESP32 Smart Traffic Controller — Setup Guide

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Arduino IDE | 2.x+ | Or PlatformIO |
| ESP32 Arduino Core | 2.0.14+ | Via Board Manager |
| PubSubClient | 2.8.0+ | Nick O'Leary |
| ArduinoJson | 6.21.3+ | Benoit Blanchon |

---

## 1. Install Arduino IDE and ESP32 Core

1. Download Arduino IDE from https://www.arduino.cc/en/software
2. Open **File → Preferences**
3. In "Additional Board Manager URLs", add:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
4. Open **Tools → Board → Boards Manager**
5. Search "esp32" and install **esp32 by Espressif Systems** (v2.0.14+)
6. Select board: **Tools → Board → ESP32 Arduino → ESP32 Dev Module**

---

## 2. Install Required Libraries

Open **Tools → Manage Libraries** and install:

| Library | Search Term | Author |
|---------|------------|--------|
| PubSubClient | `PubSubClient` | Nick O'Leary |
| ArduinoJson | `ArduinoJson` | Benoit Blanchon |

ArduinoOTA and WiFiClientSecure are built into the ESP32 Arduino core.

---

## 3. Configure WiFi and MQTT

Edit `firmware/config.h`:

```cpp
#define WIFI_SSID       "YourActualSSID"
#define WIFI_PASSWORD   "YourActualPassword"
#define MQTT_SERVER     "your-broker-hostname.com"
#define MQTT_PORT       8883
#define MQTT_USER       "traffic_system"
#define MQTT_PASS       "your-secure-mqtt-password"
```

> **Security:** Never commit `config.h` with real credentials to public repositories.
> Add `esp32/firmware/config.h` to your `.gitignore`.

---

## 4. TLS Certificate Setup

### Option A: Self-Signed CA (Local Mosquitto)

1. Generate certificates (see `docker/mosquitto/` for scripts):
   ```bash
   # Generate CA key and cert
   openssl genrsa -out ca.key 2048
   openssl req -new -x509 -days 1826 -key ca.key -out ca.crt
   
   # Generate broker key and cert
   openssl genrsa -out server.key 2048
   openssl req -new -key server.key -out server.csr
   openssl x509 -req -days 1826 -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt
   ```

2. Open `ca.crt` in a text editor and copy its full content.

3. Paste into `firmware/tls_certs.h` replacing the placeholder:
   ```cpp
   const char ROOT_CA_CERT[] PROGMEM = R"EOF(
   -----BEGIN CERTIFICATE-----
   MIIDXTCCAkWgAwIBAgI...  <-- your actual cert
   -----END CERTIFICATE-----
   )EOF";
   ```

### Option B: HiveMQ Cloud (Recommended for Beginners)

1. Sign up at https://www.hivemq.com/mqtt-cloud-broker/
2. Create a free cluster
3. Download their root CA (usually ISRG Root X1 / Let's Encrypt)
4. Update `MQTT_SERVER` in `config.h` with your cluster URL

### Option C: Skip Verification (Development Only — INSECURE)

In `main.ino`, replace `tlsClient.setCACert(ROOT_CA_CERT)` with:
```cpp
tlsClient.setInsecure();  // WARNING: No TLS verification!
```

---

## 5. Wiring

See `WIRING_DIAGRAM.md` for the full ASCII diagram. Quick reference:

| Direction | Red | Yellow | Green |
|-----------|-----|--------|-------|
| North | GPIO 2 | GPIO 4 | GPIO 5 |
| South | GPIO 12 | GPIO 13 | GPIO 14 |
| East | GPIO 18 | GPIO 19 | GPIO 21 |
| West | GPIO 22 | GPIO 23 | GPIO 25 |

Connect each LED anode → GPIO pin, cathode → 330Ω resistor → GND.

---

## 6. Upload Firmware

1. Connect ESP32 via USB
2. Select port: **Tools → Port → COMx** (Windows) or `/dev/ttyUSB0` (Linux)
3. Set Upload Speed: **115200**
4. Click **Upload** (Ctrl+U)
5. Hold BOOT button during upload if it doesn't start automatically

---

## 7. Serial Monitor Debugging

1. Open **Tools → Serial Monitor** (Ctrl+Shift+M)
2. Set baud rate to **115200**
3. Expected startup output:
   ```
   ========================================
    Smart Traffic ESP32 Firmware v1.0.0
    Junction: junction1
   ========================================
   [LED] Running startup LED test...
   [LED] Startup test complete. All RED.
   [Setup] Connecting to WiFi...
   [Setup] WiFi OK. IP: 192.168.1.xxx
   [MQTT] Connecting to your-broker.com:8883 as esp32_junction1
   [MQTT] Connected!
   [MQTT] Subscribed to: smarttraffic/junction1/signals/command
   [MQTT] Heartbeat published
   ```

---

## 8. Test Commands

Use `mosquitto_pub` to send a test command:

```bash
mosquitto_pub \
  -h your-broker.com -p 8883 \
  --cafile ca.crt \
  -u traffic_system -P your-password \
  -t smarttraffic/junction1/signals/command \
  -m '{"cmd":"set_phase","sequence_id":1001,"signals":{"north":{"phase":"GREEN","duration":30},"south":{"phase":"GREEN","duration":30},"east":{"phase":"RED","duration":35},"west":{"phase":"RED","duration":35}}}'
```

Subscribe to ACK:
```bash
mosquitto_sub \
  -h your-broker.com -p 8883 \
  --cafile ca.crt \
  -u traffic_system -P your-password \
  -t smarttraffic/junction1/signals/ack
```

See `../mqtt/test_commands.json` for all test scenarios.

---

## 9. OTA Updates

After first flash, you can update over WiFi:

1. Find ESP32's IP from Serial Monitor
2. In Arduino IDE: **Tools → Port → Network ports → esp32_junction1**
3. Upload as normal

OTA password is set in `main.ino`:
```cpp
ArduinoOTA.setPassword("ota_password_change_me");
```

---

## 10. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Upload fails | Wrong port selected | Check Device Manager → Ports |
| WiFi fails | Wrong SSID/pass | Double-check `config.h` |
| MQTT fails (state=-2) | TLS cert mismatch | Use `setInsecure()` for testing |
| MQTT fails (state=-4) | Broker unreachable | Check broker URL/port/firewall |
| LED always RED | Waiting for first command | Send test command via mosquitto_pub |
| Rapid red blink (5x) | Safety validation rejected command | Check MQTT command for conflicting greens |
| Rapid red blink (3x) | JSON parse error | Validate JSON syntax |
