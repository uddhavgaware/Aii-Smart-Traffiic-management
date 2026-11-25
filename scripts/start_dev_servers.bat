@echo off
title SmartTraffic AI Launcher
cd /d "%~dp0\.."

echo Starting FastAPI Backend (port 8000)...
start "SmartTraffic Backend" cmd /k "cd backend && venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000"

echo Starting RTX 3050 ML Inference Service (port 8001)...
start "SmartTraffic ML (CUDA)" cmd /k "set YOLO_CONFIG_DIR=%CD%\ml\.ultralytics && ml\venv\Scripts\python.exe -m uvicorn ml.inference.serve:app --host 0.0.0.0 --port 8001"

echo Starting Frontend Control Room (port 3000)...
start "SmartTraffic Frontend" cmd /k "cd frontend && set PATH=%LOCALAPPDATA%\Programs\nodejs;%PATH% && npm.cmd run dev"

echo All 3 services launched! Open http://localhost:3000
