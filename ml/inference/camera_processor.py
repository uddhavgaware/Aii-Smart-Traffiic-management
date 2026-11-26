"""
ml/inference/camera_processor.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Asynchronous single-camera processing pipeline with bounded queue (drops stale frames).
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

import cv2
import numpy as np

from .density_analyzer import DensityResult, TrafficDensityAnalyzer
from .emergency_detector import EmergencyDetector, EmergencyState, EmergencyStatus
from .model import DetectionResult, TrafficDetectionModel
from .prediction import PredictionResult, TrafficPredictor
from .tracker import TrackerResult, VehicleTracker
from .visualizer import annotate_frame

logger = logging.getLogger(__name__)

_CLAHE = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))


def preprocess_traffic_frame(frame: np.ndarray) -> np.ndarray:
    """Fast YCrCb CLAHE enhancement applied only to dark/night frames (mean luma < 85)."""
    ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
    y_channel = ycrcb[:, :, 0]
    if float(np.mean(y_channel)) >= 85.0:
        return frame
    ycrcb[:, :, 0] = _CLAHE.apply(y_channel)
    return cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)


@dataclass
class ProcessingResult:
    direction: str
    detection: DetectionResult
    tracks: TrackerResult
    density: DensityResult
    emergency: EmergencyState
    prediction: PredictionResult
    fps: float
    annotated_jpeg_b64: Optional[str] = None
    timestamp: float = 0.0


class CameraProcessor:
    """Processes frames for one approach direction using bounded latest-frame queue."""

    def __init__(
        self,
        direction: str,
        model: TrafficDetectionModel,
        config: dict,
        gpu_lock: asyncio.Lock,
        predictor: TrafficPredictor,
        on_result: Optional[Callable[[ProcessingResult], Any]] = None,
    ) -> None:
        self.direction = direction
        self.model = model
        self.config = config
        self.gpu_lock = gpu_lock
        self.predictor = predictor
        self.on_result = on_result

        self.frame_queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=4)
        self.tracker = VehicleTracker(config.get("tracking", {}))
        self.density_analyzer = TrafficDensityAnalyzer(
            config.get("density", {}),
            calibrated=bool(config.get("speed", {}).get("calibrated", False)),
        )
        self.emergency_detector = EmergencyDetector(config)
        self.roi_polygon: Optional[np.ndarray] = None
        self.latest_result: Optional[ProcessingResult] = None

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._frame_times: list[float] = []

    def set_roi(self, points: list[list[int]]) -> None:
        self.roi_polygon = np.array(points, dtype=np.int32)

    def push_frame(self, frame: np.ndarray) -> None:
        """Non-blocking push: drop oldest frame when queue is full to avoid latency buildup."""
        if self.frame_queue.full():
            try:
                self.frame_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            self.frame_queue.put_nowait(frame)
        except asyncio.QueueFull:
            pass

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._process_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def _default_roi(self, frame: np.ndarray) -> np.ndarray:
        if self.roi_polygon is not None and len(self.roi_polygon) >= 3:
            return self.roi_polygon
        h, w = frame.shape[:2]
        return np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.int32)

    def process_sync(self, frame: np.ndarray, include_snapshot: bool = False) -> ProcessingResult:
        """Run full CV pipeline on one frame (called under GPU lock in async loop)."""
        roi = self._default_roi(frame)
        infer_frame = preprocess_traffic_frame(frame)
        det = self.model.detect(infer_frame)
        tracks = self.tracker.update(det, frame)
        density = self.density_analyzer.analyze(tracks, roi, frame=frame, detections=det)
        emergency = self.emergency_detector.process(tracks, frame)

        self.predictor.update(self.direction, density.vehicle_count, density.level.value)
        pred = self.predictor.predict(self.direction)

        now = time.time()
        self._frame_times.append(now)
        self._frame_times = [t for t in self._frame_times if now - t <= 2.0]
        span = (self._frame_times[-1] - self._frame_times[0]) if len(self._frame_times) > 1 else 0.0
        fps = (len(self._frame_times) - 1) / span if span > 0.02 else 0.0

        snapshot_b64: Optional[str] = None
        if include_snapshot:
            vis = annotate_frame(frame, tracks, density, emergency, roi, self.direction)
            ok, buf = cv2.imencode(".jpg", vis, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            if ok:
                snapshot_b64 = "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")

        res = ProcessingResult(
            direction=self.direction,
            detection=det,
            tracks=tracks,
            density=density,
            emergency=emergency,
            prediction=pred,
            fps=round(fps, 1),
            annotated_jpeg_b64=snapshot_b64,
            timestamp=now,
        )
        self.latest_result = res
        return res

    async def _process_loop(self) -> None:
        while self._running:
            try:
                frame = await self.frame_queue.get()
                # Drain stale frames so we always process the latest frame
                while not self.frame_queue.empty():
                    frame = self.frame_queue.get_nowait()

                async with self.gpu_lock:
                    res = await asyncio.to_thread(self.process_sync, frame, True)

                if self.on_result:
                    maybe_coro = self.on_result(res)
                    if asyncio.iscoroutine(maybe_coro):
                        await maybe_coro
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("CameraProcessor error (%s): %s", self.direction, exc)
                await asyncio.sleep(0.2)
