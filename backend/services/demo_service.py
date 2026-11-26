"""
Clearly-labeled Demo Mode Service
=================================
Generates realistic synthetic traffic snapshots ONLY when runtime.demo_mode is True.
Per Strict Development Rule 24:
  - Demo mode must never be confused with real hardware operation.
  - When demo_mode is False, zero simulated counts/ESP32 status are produced.
"""

from __future__ import annotations

import asyncio
import base64
import math
import random
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from core.config import settings
from core.logging import get_logger
from services.analytics_service import collect_host_performance
from services.runtime import runtime
from services.signal_controller import Direction
from services.traffic_intelligence import DensityLevel, DirectionTrafficData
from services.websocket_manager import ws_manager

logger = get_logger(__name__)

try:
    import cv2  # type: ignore
    _HAS_CV2 = True
except ImportError:
    cv2 = None  # type: ignore
    _HAS_CV2 = False

_CANDIDATE_CLIPS_DIRS = [
    Path(__file__).resolve().parents[2] / "ml" / "demo_clips",
    Path(__file__).resolve().parents[1] / "demo_clips",
]
_CLIP_ASSIGNMENTS = {
    Direction.NORTH: (("vehicles.mp4", "demo_approach_1.mp4"), 0),
    Direction.SOUTH: (("vehicles-2.mp4", "demo_approach_2.mp4"), 0),
    Direction.EAST: (("vehicles.mp4", "demo_approach_1.mp4"), 60),
    Direction.WEST: (("vehicles-2.mp4", "demo_approach_2.mp4"), 80),
}


def _resolve_clip_path(filenames: tuple[str, ...]) -> Optional[Path]:
    for base in _CANDIDATE_CLIPS_DIRS:
        if not base.exists():
            continue
        for name in filenames:
            p = base / name
            if p.exists():
                return p
    return None


class DemoModeService:
    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._caps: Dict[Direction, Any] = {}
        self._http: Optional[httpx.AsyncClient] = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("demo_mode_service_started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._release_clips()
        if self._http is not None:
            await self._http.aclose()
            self._http = None
        logger.info("demo_mode_service_stopped")

    def _release_clips(self) -> None:
        for cap in self._caps.values():
            try:
                cap.release()
            except Exception:
                pass
        self._caps.clear()

    def _next_clip_jpeg(self, direction: Direction) -> Optional[bytes]:
        if not _HAS_CV2:
            return None
        cap = self._caps.get(direction)
        if cap is None:
            filenames, start_frame = _CLIP_ASSIGNMENTS[direction]
            clip_path = _resolve_clip_path(filenames)
            if clip_path is None:
                return None
            cap = cv2.VideoCapture(str(clip_path))
            if not cap.isOpened():
                return None
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
            if start_frame > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame % total_frames)
            self._caps[direction] = cap

        ok, frame = cap.read()
        if not ok or frame is None:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
        if not ok or frame is None:
            return None

        # Skip ahead a few frames per tick so motion is clearly visible at demo cadence
        cur_pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        step = 12 if total > 200 else 3
        cap.set(cv2.CAP_PROP_POS_FRAMES, (cur_pos + step) % total)

        frame = cv2.resize(frame, (640, 360))
        ok_enc, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        return buf.tobytes() if ok_enc else None

    async def _run_clip_tick(self) -> tuple[bool, Dict[Direction, bytes]]:
        """Attempt one tick using real demo video clips + ML server. Returns (ml_handled, raw_jpegs)."""
        raw_jpegs: Dict[Direction, bytes] = {}
        for d in Direction:
            jpg = self._next_clip_jpeg(d)
            if jpg:
                raw_jpegs[d] = jpg

        ml_url = (settings.ML_INFERENCE_URL or "").strip().rstrip("/")
        if not raw_jpegs or not ml_url:
            return False, raw_jpegs

        if self._http is None:
            self._http = httpx.AsyncClient(timeout=4.0)

        headers = {"X-ML-API-Key": settings.ML_API_KEY} if settings.ML_API_KEY else {}
        latencies: list[float] = []
        any_ok = False

        for d, jpg in raw_jpegs.items():
            try:
                resp = await self._http.post(
                    f"{ml_url}/infer/frame",
                    params={"direction": d.value, "publish": "false", "include_snapshot": "true"},
                    files={"file": (f"{d.value}.jpg", jpg, "image/jpeg")},
                    headers=headers,
                )
                if resp.status_code != 200:
                    continue
                res = resp.json()
                any_ok = True
                latencies.append(float(res.get("inference_ms", 15.0)))
                count = int(res.get("vehicle_count", 0))
                level_str = str(res.get("density_level", "LOW"))
                try:
                    level = DensityLevel(level_str)
                except ValueError:
                    level = DensityLevel.LOW
                density_pct = float(res.get("density_score", 0.0))
                queue_len = float(res.get("queue_length", 0.0))
                speed_est = res.get("speed_estimate")
                if speed_est is None:
                    speed_est = 0.0

                data = DirectionTrafficData(
                    direction=d,
                    vehicle_count=count,
                    density_level=level,
                    speed_estimate=float(speed_est),
                    speed_is_estimate=bool(res.get("speed_is_estimate", True)),
                    queue_length=queue_len,
                    congestion_predicted=bool(res.get("congestion_predicted", False)),
                    predicted_count=int(res.get("predicted_count", count)),
                    timestamp=time.time(),
                )
                runtime.traffic_engine.update_direction_data(data)

                await ws_manager.broadcast(
                    "traffic_update",
                    {
                        "direction": d.value,
                        "count": count,
                        "vehicle_count": count,
                        "speed": float(speed_est),
                        "speed_is_estimate": True,
                        "queue_length": queue_len,
                        "density": round(density_pct, 1),
                        "density_level": level.value,
                        "trend": "increasing" if data.congestion_predicted else "stable",
                        "congestion_predicted": data.congestion_predicted,
                    },
                )
                await ws_manager.broadcast(
                    "camera_update",
                    {
                        "direction": d.value,
                        "vehicle_count": count,
                        "density": round(density_pct, 1),
                        "fps": float(res.get("fps", 5.0)),
                        "status": "connected",
                        "detections": res.get("detections", []),
                        "snapshot": res.get("snapshot"),
                    },
                )
            except Exception:
                continue

        if any_ok:
            avg_ms = sum(latencies) / len(latencies) if latencies else 15.0
            fps_est = round(1000.0 / max(avg_ms, 1.0), 1)
            perf = collect_host_performance(inference_latency_ms=round(avg_ms, 1), detection_fps=fps_est)
            await ws_manager.broadcast("performance_metrics", perf)
            await ws_manager.broadcast("signal_update", runtime.get_signal_state_payload())
        return any_ok, raw_jpegs

    async def _loop(self) -> None:
        tick = 0
        while self._running:
            try:
                if runtime.demo_mode:
                    handled_by_clips, raw_jpegs = await self._run_clip_tick()
                    if handled_by_clips:
                        await asyncio.sleep(0.5)
                        continue

                    tick += 1
                    t = time.time()
                    for idx, d in enumerate(Direction):
                        base = int(8 + 14 * (0.5 + 0.5 * math.sin(tick * 0.25 + idx * 1.4)))
                        count = max(0, base + random.randint(-2, 3))
                        if count <= 5:
                            level = DensityLevel.LOW
                            density_pct = count * 4.0
                        elif count <= 15:
                            level = DensityLevel.NORMAL
                            density_pct = 25.0 + (count - 5) * 2.0
                        elif count <= 25:
                            level = DensityLevel.MEDIUM
                            density_pct = 48.0 + (count - 15) * 1.8
                        elif count <= 40:
                            level = DensityLevel.HIGH
                            density_pct = 68.0 + (count - 25) * 1.2
                        else:
                            level = DensityLevel.TRAFFIC_JAM
                            density_pct = 92.0

                        queue_len = round(min(100.0, count * 2.4), 1)
                        speed_est = round(max(1.5, 16.0 - count * 0.35), 1)

                        data = DirectionTrafficData(
                            direction=d,
                            vehicle_count=count,
                            density_level=level,
                            speed_estimate=speed_est,
                            speed_is_estimate=True,
                            queue_length=queue_len,
                            congestion_predicted=count > 22,
                            predicted_count=count + 2,
                            timestamp=t,
                        )
                        runtime.traffic_engine.update_direction_data(data)

                        await ws_manager.broadcast(
                            "traffic_update",
                            {
                                "direction": d.value,
                                "count": count,
                                "vehicle_count": count,
                                "speed": speed_est,
                                "speed_is_estimate": True,
                                "queue_length": queue_len,
                                "density": round(density_pct, 1),
                                "density_level": level,
                                "trend": "increasing" if count > 18 else "stable",
                                "congestion_predicted": count > 22,
                            },
                        )
                        clip_b64 = (
                            "data:image/jpeg;base64," + base64.b64encode(raw_jpegs[d]).decode("ascii")
                            if d in raw_jpegs
                            else None
                        )
                        await ws_manager.broadcast(
                            "camera_update",
                            {
                                "direction": d.value,
                                "vehicle_count": count,
                                "density": round(density_pct, 1),
                                "fps": 5.0,
                                "status": "connected",
                                "detections": [],
                                "snapshot": clip_b64,
                            },
                        )

                    perf = collect_host_performance(inference_latency_ms=18.5, detection_fps=20.0)
                    await ws_manager.broadcast("performance_metrics", perf)
                    await ws_manager.broadcast("signal_update", runtime.get_signal_state_payload())

                await asyncio.sleep(1.0 if raw_jpegs else 2.0)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("demo_loop_error", error=str(exc))
                await asyncio.sleep(2.0)


demo_service = DemoModeService()
