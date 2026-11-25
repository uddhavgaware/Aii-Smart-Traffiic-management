"""
ml/inference/serve.py
~~~~~~~~~~~~~~~~~~~~~
FastAPI inference server running on the RTX 3050 machine (port 8001).
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
import psutil

load_dotenv()
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from .multi_camera_manager import MultiCameraManager

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = os.getenv("ML_CONFIG_PATH", str(BASE_DIR / "config" / "model_config.yaml"))
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
ML_API_KEY = os.getenv("ML_API_KEY", "")

manager: Optional[MultiCameraManager] = None


def verify_api_key(x_ml_api_key: Optional[str] = Header(default=None, alias="X-ML-API-Key")) -> None:
    if ML_API_KEY and x_ml_api_key != ML_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid X-ML-API-Key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global manager
    manager = MultiCameraManager(CONFIG_PATH, BACKEND_URL, ML_API_KEY)
    await manager.start()
    yield
    await manager.stop()


app = FastAPI(title="Smart Traffic ML Inference Service", version="1.0.0", lifespan=lifespan)


class ROIUpdateRequest(BaseModel):
    direction: str
    points: List[List[int]]


@app.get("/infer/status")
async def get_status() -> dict:
    gpu_stats = {}
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if gpus:
            g = gpus[0]
            gpu_stats = {
                "name": g.name,
                "load_percent": round(g.load * 100, 1),
                "vram_used_mb": g.memoryUsed,
                "vram_total_mb": g.memoryTotal,
            }
    except Exception:
        pass

    return {
        "status": "running" if manager and manager.model else "initializing",
        "model_trained": manager.model.model_trained if manager and manager.model else False,
        "total_fps": manager.get_total_fps() if manager else 0.0,
        "cpu_percent": psutil.cpu_percent(),
        "gpu": gpu_stats,
    }


@app.get("/infer/model_info")
async def get_model_info() -> dict:
    if not manager or not manager.model:
        raise HTTPException(status_code=503, detail="Model not initialized")
    return manager.model.get_model_info()


@app.post("/infer/update_roi", dependencies=[Depends(verify_api_key)])
async def update_roi(payload: ROIUpdateRequest) -> dict:
    if not manager or payload.direction not in manager.processors:
        raise HTTPException(status_code=400, detail="Invalid direction")
    manager.processors[payload.direction].set_roi(payload.points)
    return {"updated": True, "direction": payload.direction}


@app.post("/infer/frame", dependencies=[Depends(verify_api_key)])
async def infer_frame(
    direction: str = Query(..., pattern="^(north|south|east|west)$"),
    publish: bool = Query(default=True),
    include_snapshot: bool = Query(default=False),
    file: UploadFile = File(...),
) -> dict:
    if not manager:
        raise HTTPException(status_code=503, detail="Inference manager unavailable")
    img_bytes = await file.read()
    try:
        res = await manager.process_immediate(
            direction,
            img_bytes,
            include_snapshot=include_snapshot,
            publish=publish,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    payload = manager.build_traffic_payload(res, include_snapshot=include_snapshot)
    payload.update({
        "speed_label": res.density.speed_estimate.label if res.density.speed_estimate else "ESTIMATE – uncalibrated",
        "inference_ms": round(res.detection.inference_ms, 2),
        "model_trained": res.detection.model_trained,
        "total_fps": manager.get_total_fps(),
        "prediction": {
            "expected_count": res.prediction.expected_vehicle_count,
            "expected_level": res.prediction.expected_congestion_level.value,
            "model": res.prediction.selected_model,
        },
        "emergency_alert": res.emergency.alert_level,
    })
    return payload


@app.websocket("/infer/stream")
async def infer_stream(websocket: WebSocket, direction: str = "north") -> None:
    await websocket.accept()
    if not manager or direction not in manager.processors:
        await websocket.close(code=1008)
        return
    try:
        while True:
            frame_bytes = await websocket.receive_bytes()
            res = await manager.process_immediate(direction, frame_bytes)
            await websocket.send_json({
                "direction": direction,
                "vehicle_count": res.density.vehicle_count,
                "density_level": res.density.level.value,
                "inference_ms": round(res.detection.inference_ms, 2),
                "emergency_alert": res.emergency.alert_level,
            })
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ml.inference.serve:app", host="0.0.0.0", port=8001, reload=False)
