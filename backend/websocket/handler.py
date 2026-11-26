"""
WebSocket connection handler:
  - Authenticates dashboard tokens or mobile camera pairing codes
  - Handles ping/pong keepalive
  - Relays WebRTC SDP offers/answers and ICE candidates
  - Relays mobile camera frames (camera_frame) to dashboard & local ML inference service
  - Sends live model_ack back to mobile cameras
"""

from __future__ import annotations

import asyncio
import base64
import time
from typing import Any, Optional

import httpx
from fastapi import WebSocket, WebSocketDisconnect, status

from api.traffic import ingest_traffic_payload
from core.config import settings
from core.logging import get_logger
from core.security import decode_token
from schemas.traffic import TrafficDataRequest
from services.camera_registry import camera_registry
from services.mqtt_service import mqtt_service
from services.runtime import runtime
from services.websocket_manager import ws_manager

logger = get_logger(__name__)

_LAST_ML_FORWARD: dict[str, float] = {}
_IN_FLIGHT_ML: dict[str, bool] = {}
_PENDING_ML_FRAME: dict[str, tuple[str, WebSocket]] = {}
_ML_HTTP_CLIENT: Optional[httpx.AsyncClient] = None
_ML_BACKOFF_UNTIL: float = 0.0


def _get_ml_client() -> httpx.AsyncClient:
    global _ML_HTTP_CLIENT
    if _ML_HTTP_CLIENT is None or _ML_HTTP_CLIENT.is_closed:
        _ML_HTTP_CLIENT = httpx.AsyncClient(
            timeout=2.5,
            limits=httpx.Limits(max_connections=16, max_keepalive_connections=8),
        )
    return _ML_HTTP_CLIENT


async def _ml_worker(direction: str) -> None:
    """Drain the latest pending frame for one direction without phase-beating or double HTTP hops."""
    global _ML_BACKOFF_UNTIL
    if _IN_FLIGHT_ML.get(direction, False):
        return
    _IN_FLIGHT_ML[direction] = True
    try:
        headers = {"X-ML-API-Key": settings.ML_API_KEY} if settings.ML_API_KEY else {}
        client = _get_ml_client()
        while True:
            if time.time() < _ML_BACKOFF_UNTIL or not (settings.ML_INFERENCE_URL or "").strip():
                _PENDING_ML_FRAME.pop(direction, None)
                break

            min_interval = 1.0 / max(1, int(runtime.settings_store.get("fps_per_camera", 15)))
            elapsed = time.time() - _LAST_ML_FORWARD.get(direction, 0.0)
            wait_s = (min_interval * 0.85) - elapsed
            if wait_s > 0.005:
                await asyncio.sleep(wait_s)

            pending = _PENDING_ML_FRAME.pop(direction, None)
            if pending is None:
                break

            image_data_url, camera_ws = pending
            _LAST_ML_FORWARD[direction] = time.time()

            _, b64_part = image_data_url.split(",", 1) if "," in image_data_url else ("", image_data_url)
            img_bytes = base64.b64decode(b64_part)
            resp = await client.post(
                f"{settings.ML_INFERENCE_URL}/infer/frame",
                params={"direction": direction, "publish": "false", "include_snapshot": "false"},
                files={"file": ("frame.jpg", img_bytes, "image/jpeg")},
                headers=headers,
            )
            if resp.status_code == 200:
                _ML_BACKOFF_UNTIL = 0.0
                res_json = resp.json()
                runtime.ai_engine_status = "running"
                runtime.last_inference_latency_ms = float(res_json.get("inference_ms", 0.0))
                runtime.last_detection_fps = float(res_json.get("total_fps", 0.0))

                traffic_req = TrafficDataRequest(
                    direction=res_json.get("direction", direction),
                    vehicle_count=int(res_json.get("vehicle_count", 0)),
                    density_level=res_json.get("density_level", "LOW"),
                    density_score=float(res_json.get("density_score", 0.0)),
                    speed_estimate=res_json.get("speed_estimate"),
                    speed_is_estimate=bool(res_json.get("speed_is_estimate", True)),
                    queue_length=float(res_json.get("queue_length", 0.0)),
                    congestion_predicted=bool(res_json.get("congestion_predicted", False)),
                    predicted_count=res_json.get("predicted_count"),
                    fps=float(res_json.get("fps", 0.0)),
                    detections=res_json.get("detections", []),
                    snapshot=None,
                    emergency_detected=bool(res_json.get("emergency_detected", False)),
                    emergency_type=res_json.get("emergency_type"),
                    emergency_stage2_confirmed=bool(res_json.get("emergency_stage2_confirmed", False)),
                    emergency_confidence=float(res_json.get("emergency_confidence", 0.0)),
                )
                await ingest_traffic_payload(traffic_req, db=None)

                await ws_manager.send_personal(
                    camera_ws,
                    {
                        "type": "model_ack",
                        "payload": {
                            "direction": direction,
                            "vehicle_count": res_json.get("vehicle_count", 0),
                            "density_level": res_json.get("density_level", "LOW"),
                            "inference_ms": res_json.get("inference_ms", 0.0),
                            "fps": res_json.get("fps", 0.0),
                            "detections": res_json.get("detections", []),
                            "model_trained": res_json.get("model_trained", False),
                        },
                    },
                )
            else:
                if resp.status_code >= 500:
                    _ML_BACKOFF_UNTIL = time.time() + 5.0
                    runtime.ai_engine_status = "running" if runtime.demo_mode else "stopped"
                logger.warning("ml_forward_http_error", status_code=resp.status_code, direction=direction)
    except Exception as exc:
        _ML_BACKOFF_UNTIL = time.time() + 5.0
        runtime.ai_engine_status = "running" if runtime.demo_mode else "stopped"
        logger.debug("ml_forward_failed", direction=direction, error=str(exc))
    finally:
        _IN_FLIGHT_ML[direction] = False
        if direction in _PENDING_ML_FRAME:
            asyncio.create_task(_ml_worker(direction))


async def websocket_endpoint(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    client_type = websocket.query_params.get("client_type", "dashboard")
    username = "camera_client"
    role = "viewer"

    if token:
        try:
            payload = decode_token(token)
            username = payload.get("sub", "operator")
            role = payload.get("role", "viewer")
        except Exception:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await ws_manager.connect(websocket, username=username, role=role, client_type=client_type)
    bound_directions: set[str] = set()

    await ws_manager.send_personal(
        websocket,
        {
            "type": "system_status",
            "payload": {
                "junction_status": "online",
                "ai_engine_status": runtime.ai_engine_status,
                "mqtt_connected": mqtt_service.connected,
                "esp32_connected": mqtt_service.esp32_online,
                "demo_mode": runtime.demo_mode,
                "uptime": round(time.time() - runtime.start_time, 1),
            },
        },
    )
    await ws_manager.send_personal(
        websocket,
        {"type": "signal_update", "payload": runtime.get_signal_state_payload()},
    )

    try:
        while True:
            message: dict[str, Any] = await websocket.receive_json()
            msg_type = message.get("type")
            payload = message.get("payload") or message.get("data") or {}

            if msg_type == "ping":
                await ws_manager.send_personal(websocket, {"type": "pong", "payload": {"ts": time.time()}})

            elif msg_type == "camera_frame":
                direction = str(payload.get("direction", "")).lower()
                image = payload.get("image")
                if direction in ("north", "south", "east", "west") and isinstance(image, str):
                    is_dashboard_clip = bool(token) or str(payload.get("device_id", "")).startswith("clip-")
                    if not is_dashboard_clip:
                        ws_manager.bind_camera(direction, websocket)
                    ws_manager.store_camera_frame(direction, payload)
                    if direction not in bound_directions:
                        bound_directions.add(direction)
                        await ws_manager.broadcast("camera_connected", {"direction": direction})

                    await ws_manager.broadcast(
                        "camera_frame",
                        {
                            "direction": direction,
                            "image": image,
                            "device_id": payload.get("device_id"),
                            "resolution": payload.get("resolution"),
                        },
                        exclude_cameras=True,
                        exclude=websocket,
                    )

                    # Coalesce latest frame and drain continuously up to fps_per_camera without phase drops
                    _PENDING_ML_FRAME[direction] = (image, websocket)
                    if not _IN_FLIGHT_ML.get(direction, False):
                        asyncio.create_task(_ml_worker(direction))

            elif msg_type in ("webrtc_offer", "webrtc_answer", "webrtc_ice"):
                cam_id = payload.get("camera_id", "")
                if msg_type == "webrtc_offer":
                    camera_registry.webrtc_offers[cam_id] = payload
                elif msg_type == "webrtc_answer":
                    camera_registry.webrtc_answers[cam_id] = payload
                await ws_manager.broadcast(msg_type, payload)

    except WebSocketDisconnect:
        disconnected_dir = ws_manager.disconnect(websocket)
        if disconnected_dir:
            await ws_manager.broadcast("camera_disconnected", {"direction": disconnected_dir})
    except Exception as exc:
        logger.warning("ws_handler_error", error=str(exc))
        disconnected_dir = ws_manager.disconnect(websocket)
        if disconnected_dir:
            await ws_manager.broadcast("camera_disconnected", {"direction": disconnected_dir})
