"""
ml/inference/multi_camera_manager.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Manages 4 CameraProcessor instances sharing a single CUDA TrafficDetectionModel.
Coordinates round-robin GPU inference and posts results to the FastAPI backend.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Dict, Optional

import cv2
import httpx
import numpy as np
import yaml

from .camera_processor import CameraProcessor, ProcessingResult
from .emergency_detector import EmergencyStatus
from .model import TrafficDetectionModel
from .prediction import TrafficPredictor

logger = logging.getLogger(__name__)


class MultiCameraManager:
    DIRECTIONS = ("north", "south", "east", "west")

    def __init__(self, config_path: str, backend_url: str, ml_api_key: str = "") -> None:
        with open(config_path, "r") as fh:
            self.config = yaml.safe_load(fh)
        self.config_path = config_path
        self.backend_url = backend_url.rstrip("/")
        self.ml_api_key = ml_api_key or os.getenv("ML_API_KEY", "")

        self.model: Optional[TrafficDetectionModel] = None
        self.gpu_lock = asyncio.Lock()
        self.predictor = TrafficPredictor(
            method=self.config.get("prediction", {}).get("method", "exponential_smoothing"),
            horizon_seconds=int(self.config.get("prediction", {}).get("horizon", 45)),
        )
        self.processors: Dict[str, CameraProcessor] = {}
        self._http: Optional[httpx.AsyncClient] = None

    async def start(self) -> None:
        self.model = TrafficDetectionModel(self.config_path)
        self._http = httpx.AsyncClient(timeout=5.0)
        for d in self.DIRECTIONS:
            proc = CameraProcessor(
                direction=d,
                model=self.model,
                config=self.config,
                gpu_lock=self.gpu_lock,
                predictor=self.predictor,
                on_result=self._publish_single,
            )
            self.processors[d] = proc
            await proc.start()
        logger.info("MultiCameraManager started for 4 directions.")

    async def stop(self) -> None:
        for proc in self.processors.values():
            await proc.stop()
        if self._http:
            await self._http.aclose()

    def decode_frame(self, frame_bytes: bytes) -> Optional[np.ndarray]:
        arr = np.frombuffer(frame_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return frame

    async def push_frame(self, direction: str, frame_bytes: bytes) -> None:
        if direction not in self.processors:
            raise ValueError(f"Invalid direction: {direction}")
        frame = self.decode_frame(frame_bytes)
        if frame is not None:
            self.processors[direction].push_frame(frame)

    async def process_immediate(
        self,
        direction: str,
        frame_bytes: bytes,
        include_snapshot: bool = False,
        publish: bool = True,
    ) -> ProcessingResult:
        if direction not in self.processors:
            raise ValueError(f"Invalid direction: {direction}")
        frame = self.decode_frame(frame_bytes)
        if frame is None:
            raise ValueError("Invalid image bytes")
        async with self.gpu_lock:
            res = await asyncio.to_thread(self.processors[direction].process_sync, frame, include_snapshot)
        if publish:
            asyncio.create_task(self._publish_single(res))
        return res

    def build_traffic_payload(self, res: ProcessingResult, include_snapshot: bool = True) -> dict:
        h, w = res.detection.frame_shape[:2]
        norm_dets = []
        source_items = res.tracks.tracks if res.tracks.tracks else res.detection.detections
        for idx, item in enumerate(source_items):
            x1, y1, x2, y2 = item.bbox_xyxy
            track_id = getattr(item, "track_id", idx)
            norm_dets.append({
                "id": str(track_id),
                "trackId": track_id,
                "class": item.class_name,
                "confidence": round(item.confidence, 3),
                "bbox": [
                    round(float(x1) / max(w, 1), 4),
                    round(float(y1) / max(h, 1), 4),
                    round(float(x2 - x1) / max(w, 1), 4),
                    round(float(y2 - y1) / max(h, 1), 4),
                ],
            })

        confirmed_em = [e for e in res.emergency.active_emergencies if e.status == EmergencyStatus.CONFIRMED]
        any_em = res.emergency.active_emergencies
        top_em = confirmed_em[0] if confirmed_em else (any_em[0] if any_em else None)

        return {
            "direction": res.direction,
            "vehicle_count": res.density.vehicle_count,
            "density_level": res.density.level.value,
            "density_score": round(min(100.0, res.density.weighted_score * 100.0), 1),
            "speed_estimate": round(res.density.speed_estimate.value, 2) if res.density.speed_estimate else None,
            "speed_is_estimate": res.density.speed_estimate.is_estimate if res.density.speed_estimate else True,
            "queue_length": round(res.density.queue_length, 1),
            "congestion_predicted": res.prediction.possible_traffic_jam,
            "predicted_count": res.prediction.expected_vehicle_count,
            "fps": res.fps,
            "detections": norm_dets,
            "snapshot": res.annotated_jpeg_b64 if include_snapshot else None,
            "emergency_detected": top_em is not None,
            "emergency_type": top_em.class_name if top_em else None,
            "emergency_stage2_confirmed": bool(confirmed_em),
            "emergency_confidence": round(top_em.confidence, 3) if top_em else 0.0,
        }

    async def _publish_single(self, res: ProcessingResult) -> None:
        if not self._http:
            return
        payload = self.build_traffic_payload(res, include_snapshot=res.annotated_jpeg_b64 is not None)
        headers = {"X-ML-API-Key": self.ml_api_key} if self.ml_api_key else {}
        try:
            await self._http.post(f"{self.backend_url}/api/traffic/update", json=payload, headers=headers)
        except Exception as exc:
            logger.debug("Backend publish deferred (%s): %s", res.direction, exc)

    def get_total_fps(self) -> float:
        return round(sum(p.latest_result.fps for p in self.processors.values() if p.latest_result), 2)
