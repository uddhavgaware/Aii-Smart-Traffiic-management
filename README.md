# 🚦 AI-Based Intelligent Traffic Management System

> **Industry-Level | Computer Vision | Machine Learning | ESP32 | Cloud Web Application**

A complete, professional-grade AI-based intelligent traffic management system for a four-way junction, featuring real-time computer vision, adaptive signal control, emergency vehicle priority, and a cloud-hosted web dashboard.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CLOUD INFRASTRUCTURE                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Frontend   │  │   Backend    │  │   MQTT Broker        │  │
│  │  React/Vite  │  │  FastAPI     │  │  (EMQX/Mosquitto)   │  │
│  │  TypeScript  │◄─►  WebSocket  │  │   TLS Secured        │  │
│  │  Tailwind    │  │  REST API    │  └──────────┬───────────┘  │
│  └──────────────┘  │  PostgreSQL  │             │               │
│                    │  Redis Cache │             │               │
│                    └──────┬───────┘             │               │
└───────────────────────────┼─────────────────────┼───────────────┘
                            │ Secure Tunnel        │ MQTT/TLS
                    ┌───────┴───────┐             │
                    │  LOCAL GPU    │             │
                    │  INFERENCE    │        ┌────┴────┐
                    │  RTX 3050     │        │  ESP32  │
                    │  PyTorch      │        │  12 LEDs│
                    │  OpenCV       │        └─────────┘
                    └───────────────┘
                            ▲
                   WebRTC Streams
                    ┌───────────────────────────────┐
                    │ 📱 North │ 📱 South │ 📱 East │ 📱 West │
                    └───────────────────────────────┘
```

## 📋 Key Features

| Feature | Description |
|---------|-------------|
| 🎥 **4-Camera System** | Four mobile phones as independent traffic cameras via WebRTC |
| 🤖 **AI Detection** | Custom-trained YOLOv8 model: cars, motorcycles, buses, trucks, rickshaws |
| 🚑 **Emergency Priority** | Ambulance & fire brigade detection with visual confirmation |
| 🚦 **Adaptive Signals** | Intelligent signal timing based on traffic density & predictions |
| 📊 **Analytics Dashboard** | Professional control-room UI with real-time metrics |
| 🔌 **ESP32 Hardware** | 12 LEDs (4×RGB signals) controlled via MQTT over TLS |
| 🗺️ **Digital Twin** | Interactive 2D junction visualization |
| 🔐 **Security** | JWT auth, HTTPS, MQTT TLS, rate limiting |

## 🗂️ Project Structure

```
smart-traffic-management/
├── frontend/           # React + TypeScript + Vite + Tailwind
├── backend/            # Python FastAPI + PostgreSQL + Redis
├── ml/                 # PyTorch ML pipeline + YOLOv8 + ByteTrack
├── esp32/              # Arduino/MicroPython firmware
├── tests/              # Unit, integration, performance, scenarios
├── docs/               # Architecture, API, hardware guides
├── docker/             # Docker + docker-compose
└── scripts/            # Setup, deployment, utility scripts
```

## 🚀 Quick Start

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Backend + ML |
| Node.js | 18+ | Frontend |
| PostgreSQL | 15+ | Database |
| Redis | 7+ | Cache/State |
| CUDA | 11.8+ | GPU inference |
| Docker | 24+ | Containerization |

### 1. Clone & Setup

```bash
git clone <repo-url>
cd smart-traffic-management
cp .env.example .env
# Edit .env with your configuration
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload
```

### 3. ML Inference Service

```bash
cd ml
pip install -r requirements.txt
python inference/serve.py
```

### 4. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 5. ESP32 Firmware

See [esp32/documentation/SETUP.md](esp32/documentation/SETUP.md)

### 6. Docker (Full Stack)

```bash
docker-compose up -d
```

## 🔌 Hardware Setup

### ESP32 LED Pin Mapping

| Direction | Signal | GPIO Pin |
|-----------|--------|----------|
| North | Red | GPIO 2 |
| North | Yellow | GPIO 4 |
| North | Green | GPIO 5 |
| South | Red | GPIO 12 |
| South | Yellow | GPIO 13 |
| South | Green | GPIO 14 |
| East | Red | GPIO 18 |
| East | Yellow | GPIO 19 |
| East | Green | GPIO 21 |
| West | Red | GPIO 22 |
| West | Yellow | GPIO 23 |
| West | Green | GPIO 25 |

### Signal Transition Safety

```
ACTIVE GREEN → YELLOW (3s) → ALL-RED (2s) → NEXT GREEN
```
Opposing pairs allowed: North+South, East+West

## 📱 Camera Setup

1. Open web app on mobile browser
2. Navigate to `/camera`
3. Scan QR code or enter junction code
4. Select direction (North/South/East/West)
5. Grant camera permission
6. Start streaming

## 🧠 ML Architecture

- **Base Model**: YOLOv8n (fine-tuned)
- **Tracker**: ByteTrack
- **Vehicle Classes**: Car, Motorcycle, Bus, Truck, Auto Rickshaw, Ambulance, Fire Brigade
- **Inference**: CUDA FP16 on RTX 3050
- **Target FPS**: 5 FPS/camera × 4 cameras = 20 processed frames/sec

## 📊 Traffic Density Classification

| Level | Criteria |
|-------|---------|
| LOW | <5 vehicles, moving freely |
| NORMAL | 5–15 vehicles, normal speed |
| MEDIUM | 15–25 vehicles, reduced speed |
| HIGH | 25–40 vehicles, slow movement |
| TRAFFIC JAM | 40+ vehicles, near-stationary |

## 🏆 Development Phases

- [x] Phase 1: Requirements & Architecture
- [ ] Phase 2: Frontend Foundation
- [ ] Phase 3: Backend
- [ ] Phase 4: Camera Integration
- [ ] Phase 5: Computer Vision
- [ ] Phase 6: Custom ML
- [ ] Phase 7: Traffic Intelligence
- [ ] Phase 8: ESP32 Integration
- [ ] Phase 9: Analytics & Optimization
- [ ] Phase 10: Final Delivery

## 📄 License

MIT License — See [LICENSE](LICENSE)

## 👥 Contributors

Built as an industry-level engineering project.

---

> ⚠️ **Demo Mode**: When ESP32 or cameras are unavailable, the system operates in clearly-labelled Demo Mode using sample video and simulated responses. Demo Mode is never confused with real hardware operation.
