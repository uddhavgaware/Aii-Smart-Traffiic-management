# Installation & Camera Setup Guide (Windows RTX 3050 + i5)

## 1. Software Prerequisites
- **Python 3.11** (64-bit) with pip
- **Node.js 20 LTS** + npm
- **PostgreSQL 15** & **Redis 7** (or Docker Desktop running `postgres`, `redis`, `mqtt-broker`)
- **NVIDIA CUDA 11.8 / 12.x** drivers for RTX 3050 6GB

## 2. Environment Setup
```powershell
copy .env.example .env
python scripts\generate_secrets.py
# Paste generated SECRET_KEY, ML_API_KEY, MQTT_PASSWORD into .env
```

## 3. Install Dependencies
Run `scripts\setup_dev.bat` or manually:
- **Backend**: `cd backend && pip install -r requirements.txt`
- **ML (CUDA)**: Install PyTorch CUDA wheel (`pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118`) then `pip install -r ml/requirements.txt`
- **Frontend**: `cd frontend && npm install`

## 4. Initialize Database & Admin User
```powershell
cd backend
alembic upgrade head
cd ..
python scripts\create_admin_user.py
```

## 5. Run Services
```powershell
# Terminal 1: Backend API (Port 8000)
cd backend && uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 2: Local RTX 3050 ML Service (Port 8001)
uvicorn ml.inference.serve:app --host 0.0.0.0 --port 8001

# Terminal 3: Frontend Dashboard (Port 3000)
cd frontend && npm run dev
```

## 6. Mobile Camera Setup (4 Phones)
1. Open `https://<your-domain>/camera` (HTTPS required by mobile browsers for `getUserMedia` outside `localhost`).
2. Scan the QR code generated on the **Cameras** page (or manually select North/South/East/West + enter the Junction Code).
3. Tap **Start Live Streaming**. Repeat on all four Android phones.
4. For phones on cellular networks, configure a TURN server (`coturn` / Metered TURN) in `.env`.
