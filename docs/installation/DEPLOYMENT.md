# Online Cloud Deployment Guide

This guide deploys the **Cloud Frontend + Cloud Backend + PostgreSQL + Redis** online while keeping **YOLOv8 GPU inference** on your local **RTX 3050** laptop (or migrating it to a cloud GPU VM later).

---

## Step 1: Push Project to GitHub
Make sure `.env` and `smarttraffic.db` are **not** committed (already excluded by `.gitignore`).

```bash
git init
git add .
git commit -m "Initial Smart Traffic Management System"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

---

## Step 2: Deploy Backend + PostgreSQL + Redis on Render
1. Open [Render Dashboard](https://dashboard.render.com) → **New +** → **Blueprint** and connect your GitHub repository.
2. Render automatically reads `render.yaml` and creates:
   - `smarttraffic-backend` (Docker web service using `docker/backend/Dockerfile`)
   - `smarttraffic-db` (Managed PostgreSQL)
   - `smarttraffic-redis` (Managed Redis)
3. Set `ADMIN_PASSWORD` when prompted (initial `admin` user is bootstrapped automatically on first startup).
4. Copy your Render backend URL, e.g. `https://smarttraffic-backend.onrender.com`.

*(Alternative: on **Railway**, deploy from GitHub using `railway.toml`, add PostgreSQL + Redis plugins, and set `SECRET_KEY`, `ML_API_KEY`, and `ADMIN_PASSWORD`.)*

---

## Step 3: Deploy Frontend on Vercel (HTTPS + WSS)
1. Open [Vercel](https://vercel.com/new) → import the same GitHub repository.
2. Set **Root Directory** to `frontend`.
3. Framework preset: **Vite** (`npm run build`, output `dist`; SPA routes handled by `frontend/vercel.json`).
4. Add Environment Variables:
   - `VITE_API_URL=https://smarttraffic-backend.onrender.com`
   - `VITE_WS_URL=wss://smarttraffic-backend.onrender.com`
5. Deploy and copy your Vercel URL, e.g. `https://smarttraffic-ui.vercel.app`.
6. Update `CORS_ORIGINS` on Render to include your Vercel URL:
   `["https://smarttraffic-ui.vercel.app","http://localhost:3000"]`

---

## Step 4: Connect Your Local RTX 3050 GPU Inference Service (`:8001`)
1. Run the ML server locally:
   ```powershell
   ml\venv\Scripts\python.exe -m uvicorn ml.inference.serve:app --host 127.0.0.1 --port 8001
   ```
   Make sure `BACKEND_URL=https://smarttraffic-backend.onrender.com` and `ML_API_KEY=<same-key-as-render>` are set in `.env`.
2. Expose port `8001` securely to your Render backend:
   ```powershell
   cloudflared tunnel --url http://127.0.0.1:8001
   ```
   *(For a permanent URL without restarts, create a Named Cloudflare Tunnel on your Cloudflare account.)*
3. Set `ML_INFERENCE_URL` on Render to that HTTPS tunnel URL.

---

## Step 5: Connect Phones & ESP32
- **Four Mobile Phones (any Wi-Fi / 4G / 5G network)**:
  Open `https://smarttraffic-ui.vercel.app/camera` (or scan the QR code on `/cameras`) — camera permissions and `wss://` work natively over trusted HTTPS.
- **TURN Relay (for peer-to-peer WebRTC across cellular NATs)**:
  Set `TURN_SERVER_URL`, `TURN_USERNAME`, and `TURN_CREDENTIAL` on Render (e.g., `coturn` or Metered TURN).
- **ESP32**:
  Point `MQTT_SERVER` in `esp32/firmware/config.h` to a TLS MQTT broker (HiveMQ Cloud / EMQX Cloud / TLS Mosquitto) on port `8883` and match `MQTT_*` environment variables on Render.
