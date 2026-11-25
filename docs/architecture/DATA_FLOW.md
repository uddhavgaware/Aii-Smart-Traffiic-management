# End-to-End Data Flow

1. **Video Capture (`frontend/src/pages/MobileCamera.tsx`)**:
   - Each phone opens `/camera`, grants camera permissions, pairs via QR code or manual code, and negotiates WebRTC (`RTCPeerConnection` + STUN/TURN) while sampling frames (~5 FPS) over WebSocket `camera_frame`.
2. **Ingestion & Inference (`backend/websocket/handler.py` → `ml/inference/serve.py`)**:
   - Frames enter bounded per-direction queues (`maxsize=4`, dropping stale frames) inside `CameraProcessor` and share one CUDA YOLOv8n instance via `MultiCameraManager`.
3. **Analysis & Prediction (`ml/inference/`)**:
   - `TrafficDetectionModel` → `VehicleTracker` (ByteTrack) → `TrafficDensityAnalyzer` + `EmergencyDetector` + `TrafficPredictor`.
4. **Traffic Intelligence & Safety (`backend/services/`)**:
   - ML posts structured metrics to `POST /api/traffic/update`.
   - `TrafficIntelligenceEngine` computes density-weighted signal timing recommendations and explainable reasoning.
   - `SignalSafetyController` validates min/max green (`15s–120s`), starvation (`180s`), and enforces `GREEN → YELLOW (3s) → ALL_RED (2s) → NEXT_GREEN`.
5. **Hardware Execution (`backend/services/mqtt_service.py` → `esp32/firmware/main.ino`)**:
   - Validated command published over MQTT TLS to `smarttraffic/junction1/signals/command`.
   - ESP32 validates command independently (`signal_safety.h`), drives the 12 GPIO LEDs, and replies on `signals/ack`.
6. **Dashboard & Digital Twin (`frontend/src/`)**:
   - Backend broadcasts `traffic_update`, `camera_update`, `signal_update`, `ai_decision`, `emergency_alert`, and `performance_metrics` over `/ws` to update live feeds, bounding boxes, and the 2D Canvas Digital Twin.
