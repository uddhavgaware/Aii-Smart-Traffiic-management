# System Architecture — AI-Based Intelligent Traffic Management System

## 1. Project Overview
This project implements a real-time **AI-Based Intelligent Traffic Management System** for a four-way traffic junction using:
- **Four Android mobile phones** acting as cross-network cameras (`/camera` PWA via WebRTC + STUN/TURN + WebSocket).
- **Custom Hybrid Computer Vision & ML** running on a local **NVIDIA RTX 3050 6GB** GPU (`YOLOv8n` + `ByteTrack` + optical-flow speed estimation + two-stage emergency vehicle verification + rolling prediction comparator).
- **Deterministic Signal Safety Controller** enforcing `GREEN → YELLOW → ALL_RED → NEXT_GREEN`, compatible phase pairs (`North+South`, `East+West`), starvation prevention (`MAX_WAIT_TIME = 180s`), and safe emergency overrides.
- **Cloud-ready FastAPI Backend + PostgreSQL + Redis + MQTT TLS**.
- **Physical ESP32 Microcontroller** driving **12 LEDs** (4 approaches × Red/Yellow/Green) with independent hardware-level safety validation.

## 2. Hybrid Deployment Topology
```
[4x Mobile Cameras (Different Networks)]
       │ WebRTC (STUN/TURN) + WSS frame relay
       ▼
[Cloud Backend (FastAPI) + PostgreSQL + Redis] ◄──────► [React Control Room UI]
       │ HTTPS / X-ML-API-Key                    │ MQTT over TLS (8883)
       ▼                                         ▼
[Local RTX 3050 GPU Inference Service]       [ESP32 + 12 Physical LEDs]
```

## 3. ML Architecture & Vehicle Classes
- **Object Detection**: Modular `TrafficDetectionModel` (`ml/inference/model.py`) wrapping Ultralytics YOLOv8n with FP16 CUDA inference and model warm-up.
- **Required 7 Classes**: `0: car`, `1: motorcycle`, `2: bus`, `3: truck`, `4: auto_rickshaw`, `5: ambulance`, `6: fire_brigade`. Police vehicles, bicycles, and cycle rickshaws do not receive emergency priority.
- **Multi-Object Tracking**: ByteTrack (`supervision`) with unique track IDs and cross-line counting to eliminate duplicate counts.
- **Density Classification**: `LOW`, `NORMAL`, `MEDIUM`, `HIGH`, `TRAFFIC_JAM` combining vehicle count, queue length, ROI coverage, and relative speed (`ESTIMATE – uncalibrated` unless homography calibration is configured).
- **Traffic Prediction (30–60s horizon)**: Compares Moving Average, Exponential Smoothing, Random Forest, and Gradient Boosting on rolling RMSE (`ml/inference/prediction.py`).
- **Two-Stage Emergency Intelligence**:
  - Stage 1: Vehicle class (`ambulance` / `fire_brigade`).
  - Stage 2: 30-frame temporal ROI luminance flashing + HSV red/blue beacon analysis (`CONFIRMED > 0.7`, `UNCONFIRMED 0.3–0.7`, `NORMAL <= 0.3`).

## 4. Database Design (`backend/models/`)
| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `users` | RBAC authentication | `username`, `email`, `hashed_password`, `role` (`admin`/`operator`/`viewer`) |
| `cameras` | 4-way camera registry | `unique_id`, `direction` (unique), `status`, `ip_address`, `last_seen` |
| `traffic_events` | Historical counts & density | `timestamp`, `direction`, `vehicle_count`, `density_level`, `speed_estimate`, `queue_length` |
| `signal_events` | Phase & manual override audit | `timestamp`, `direction`, `phase`, `duration`, `reason`, `triggered_by`, `mode` |
| `emergency_events` | Stage 1/2 emergency log | `timestamp`, `direction`, `vehicle_type`, `stage1_detected`, `stage2_confirmed`, `confidence`, `cleared_at` |
| `system_events` | Notification & alert history | `timestamp`, `event_type`, `severity`, `message`, `acknowledged` |

## 5. Security Architecture
- JWT HS256 Bearer authentication + bcrypt password hashing (`backend/core/security.py`).
- Role-based guards (`admin`, `operator`, `viewer`) and `X-ML-API-Key` protection for ML ingestion.
- Rate limiting (`slowapi` 100 req/min), CORS allowlists, MQTT TLS (`8883`), WebRTC DTLS-SRTP.
- Secrets strictly isolated in `.env` (never embedded in frontend code or ESP32 docs).
