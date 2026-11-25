# REST & WebSocket API Reference

Interactive Swagger documentation is exposed at `/api/docs` when the backend is running.

## Authentication (`/api/auth`)
- `POST /api/auth/login` — Body `{ "username", "password" }` → `{ "access_token", "refresh_token", "expires_in" }`
- `POST /api/auth/refresh` — Body `{ "refresh_token" }`
- `GET /api/auth/me` — Current user details (Bearer JWT)
- `POST /api/auth/logout`

## Cameras & WebRTC (`/api/cameras`)
- `GET /api/cameras` — List registered approach cameras
- `GET /api/cameras/junction-code` — Active QR pairing code
- `GET /api/cameras/qr/{direction}` — PNG QR code for North/South/East/West
- `POST /api/cameras/register` — Register camera `{ direction, device_id, junction_code, allow_replace }`
- `POST /api/cameras/{direction}/reconnect` — Trigger reconnect
- `DELETE /api/cameras/{direction}` — Unregister (Admin)
- `GET /api/cameras/webrtc/config` — STUN/TURN ICE servers
- `POST /api/cameras/webrtc/offer|answer|ice` — SDP/ICE signaling relay

## Traffic & Analytics (`/api/traffic`, `/api/analytics`)
- `GET /api/traffic/current` — Live metrics per direction
- `POST /api/traffic/update` — ML ingestion (`X-ML-API-Key` or admin/operator JWT)
- `GET /api/traffic/history?direction=&hours=24`
- `GET /api/traffic/analytics?period=24h`
- `GET /api/traffic/export?from=&to=` — Downloadable CSV report
- `GET /api/analytics/summary|vehicles|density|signals|performance|export/csv`

## Signals & Hardware (`/api/signals`, `/api/hardware`)
- `GET /api/signals/state` — Active phases, countdowns, mode
- `POST /api/signals/mode` — Switch `{ "mode": "AUTO" | "MANUAL" }`
- `POST /api/signals/override` — Manual transition `{ direction, phase, duration }`
- `GET /api/signals/config` & `PUT /api/signals/config` / `PATCH /api/signals/timing`
- `GET /api/signals/history`
- `GET /api/hardware/status`, `POST /api/hardware/reboot`, `POST /api/hardware/test`

## Emergency & System (`/api/emergency`, `/api/system`)
- `GET /api/emergency/current`, `POST /api/emergency/alert`, `POST /api/emergency/clear`, `GET /api/emergency/history`
- `GET /api/system/health`, `GET /api/system/status`, `GET /api/system/metrics`, `GET/PATCH /api/system/settings`, `POST /api/system/demo/toggle`, `GET /api/system/events`

## WebSocket (`/ws?token=<jwt>`)
Broadcast event types: `system_status`, `signal_update`, `traffic_update`, `camera_update`, `camera_frame`, `emergency_alert`, `ai_decision`, `esp32_status`, `performance_metrics`, `notification`.
