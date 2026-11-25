# MQTT Protocol Specification (ESP32 ↔ Backend)

## Transport & Security
- **Protocol**: MQTT v3.1.1 over TLS 1.2+
- **Port**: `8883` (TLS)
- **Authentication**: Username + Password + CA Certificate verification (`tls_certs.h`)
- **QoS**: `1` (At least once delivery for signal commands and ACKs)
- **Last Will & Testament (LWT)**: Topic `smarttraffic/junction1/status`, Payload `{"state":"offline"}`, Retained

## Topics

| Topic | Direction | Purpose |
|-------|-----------|---------|
| `smarttraffic/junction1/signals/command` | Backend → ESP32 | Validated signal phase command |
| `smarttraffic/junction1/signals/ack` | ESP32 → Backend | Execution acknowledgement or safety rejection |
| `smarttraffic/junction1/status` | ESP32 → Backend | 10-second heartbeat (`online`, RSSI, heap, LED phases) |
| `smarttraffic/junction1/error` | ESP32 → Backend | Firmware parse or safety rejection alerts |
| `smarttraffic/junction1/system/command` | Backend → ESP32 | Maintenance commands (`reboot`, `test_leds`) |

## Command Payload (`signals/command`)

```json
{
  "cmd": "set_phase",
  "sequence_id": 1001,
  "mode": "AUTO",
  "signals": {
    "north": {"phase": "GREEN", "duration": 45},
    "south": {"phase": "GREEN", "duration": 45},
    "east":  {"phase": "RED",   "duration": 50},
    "west":  {"phase": "RED",   "duration": 50}
  }
}
```

## Acknowledgement Payload (`signals/ack`)

```json
{
  "ack": true,
  "sequence_id": 1001,
  "executed_at": 42150,
  "junction_id": "junction1",
  "current_state": {
    "north": {"phase": "GREEN"},
    "south": {"phase": "GREEN"},
    "east":  {"phase": "RED"},
    "west":  {"phase": "RED"}
  }
}
```

## Firmware Safety Checks
Even if the backend sends a malformed or unsafe command, `esp32/firmware/signal_safety.h` independently rejects:
1. Simultaneous `GREEN` or `YELLOW` across perpendicular axes (`N/S` vs `E/W`).
2. `GREEN` durations outside `[15000ms, 120000ms]`.
3. Direct `GREEN → RED` transitions without `YELLOW` (`3000ms`) + `ALL_RED` (`2000ms`).
