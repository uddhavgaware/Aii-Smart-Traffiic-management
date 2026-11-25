# Operator User Guide & Demonstration Workflow

## 1. Logging In
Open the dashboard at `http://localhost:3000/login` and sign in with the admin credentials created via `scripts/create_admin_user.py`.

## 2. Control Room Overview (`/`)
- **Top Status Bar**: Displays Junction, AI Engine, ESP32 MQTT, and 4 individual camera indicators (`N/S/E/W`), live clock, and notification center.
- **2×2 Camera Grid**: Shows live feeds, YOLOv8 bounding boxes, track IDs, vehicle counts, density level, and FPS. Supports per-direction filtering and fullscreen inspection.
- **2D Digital Twin**: Canvas representation synced to actual detected vehicle counts, queue percentages, and live ESP32 phases.
- **AI Decision Panel**: Explains why `N+S` or `E+W` received green time.

## 3. Automatic vs Manual Signal Control (`/signals`)
- In **AUTO** mode, `TrafficIntelligenceEngine` updates adaptive timings every 5s while `SignalSafetyController` enforces bounds and starvation prevention.
- Switching to **MANUAL** allows operators to trigger safe transitions (`GREEN → YELLOW (3s) → ALL_RED (2s) → NEXT_GREEN`). Conflicting greens are impossible.

## 4. Emergency Workflow (`/emergency`)
- Stage 1 flags `ambulance` or `fire_brigade` detections.
- Stage 2 evaluates 30 frames of flashing beacon luminance + color before confirming (`>0.7`). Unconfirmed detections clearly display uncertainty without triggering false overrides.
- Once confirmed, the junction safely clears active greens and opens the emergency lane until cleared.

## 5. Demonstration Mode (No Physical Hardware)
- Navigate to **Settings** → **Enable Demo Mode** when showcasing UI workflows without 4 phones or an ESP32.
- An amber banner clearly labels the session as simulated data. Disable Demo Mode for real operation.
