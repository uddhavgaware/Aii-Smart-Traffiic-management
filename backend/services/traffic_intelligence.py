"""
Traffic Intelligence Engine
============================
Receives detected traffic data from the ML inference service.
Applies prediction, density analysis, and emergency logic to produce
SignalRecommendations for the SignalSafetyController.

The ML model recommends → Safety controller validates → ESP32 executes.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional
from collections import deque

from .signal_controller import (
    SignalSafetyController, SignalRecommendation, Direction,
    COMPATIBLE_PAIRS
)

logger = logging.getLogger(__name__)


class DensityLevel(str):
    LOW = "LOW"
    NORMAL = "NORMAL"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    TRAFFIC_JAM = "TRAFFIC_JAM"


DENSITY_WEIGHTS = {
    DensityLevel.LOW: 1,
    DensityLevel.NORMAL: 2,
    DensityLevel.MEDIUM: 3,
    DensityLevel.HIGH: 4,
    DensityLevel.TRAFFIC_JAM: 5,
}


@dataclass
class DirectionTrafficData:
    """Latest traffic data for one direction."""
    direction: Direction
    vehicle_count: int = 0
    density_level: str = DensityLevel.LOW
    speed_estimate: Optional[float] = None  # None if uncalibrated
    speed_is_estimate: bool = True
    queue_length: float = 0.0  # 0–100 (percentage of ROI)
    congestion_predicted: bool = False
    predicted_count: Optional[int] = None
    emergency_detected: bool = False
    emergency_type: Optional[str] = None
    emergency_stage2_confirmed: bool = False
    emergency_confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)

    @property
    def is_stale(self) -> bool:
        return (time.time() - self.timestamp) > 10.0  # 10s stale threshold

    @property
    def density_weight(self) -> int:
        return DENSITY_WEIGHTS.get(self.density_level, 1)

    @property
    def priority_score(self) -> float:
        """Combined priority score for signal optimization."""
        score = (
            self.density_weight * 0.4 +
            (self.vehicle_count / 50.0) * 0.3 +  # normalized to 50 vehicles
            (self.queue_length / 100.0) * 0.3
        )
        return min(score, 1.0)


@dataclass
class AIDecisionExplanation:
    """Human-readable explanation of the signal decision."""
    selected_pair: list[str]
    primary_reason: str
    metrics: dict
    timestamp: float = field(default_factory=time.time)
    is_emergency: bool = False
    emergency_detail: Optional[str] = None

    def to_text(self) -> str:
        dirs = " + ".join(d.upper() for d in self.selected_pair)
        if self.is_emergency and self.emergency_detail:
            return (
                f"{dirs} direction selected because {self.emergency_detail}. "
                f"Emergency override active — traffic safety transition enforced."
            )
        return (
            f"{dirs} direction selected because {self.primary_reason}. "
            f"Metrics: vehicle count={self.metrics.get('vehicle_count', 'N/A')}, "
            f"density={self.metrics.get('density', 'N/A')}, "
            f"queue={self.metrics.get('queue_length', 'N/A')}%, "
            f"predicted congestion={'yes' if self.metrics.get('congestion_predicted') else 'no'}."
        )


class TrafficIntelligenceEngine:
    """
    Central traffic intelligence coordinator.
    
    Flow:
        ML service → update_direction_data() → compute_signal_recommendation()
                   → signal_controller.accept_recommendation()
    
    Runs as async background task, polling for updates.
    """

    # Green time scaling by density
    GREEN_TIME_TABLE = {
        DensityLevel.LOW: 20,
        DensityLevel.NORMAL: 30,
        DensityLevel.MEDIUM: 50,
        DensityLevel.HIGH: 80,
        DensityLevel.TRAFFIC_JAM: 110,
    }

    def __init__(self, signal_controller: SignalSafetyController):
        self.signal_controller = signal_controller
        self.direction_data: dict[Direction, DirectionTrafficData] = {
            d: DirectionTrafficData(direction=d) for d in Direction
        }
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_decision_time = 0.0
        self.decision_interval = 5.0  # Recompute recommendation every 5s
        self.last_explanation: Optional[AIDecisionExplanation] = None

        # History for prediction (direction → deque of (timestamp, count, density_weight))
        self._history: dict[Direction, deque] = {
            d: deque(maxlen=60) for d in Direction  # ~5 minutes at 5s interval
        }

        # Active emergency tracking
        self._active_emergency_direction: Optional[Direction] = None
        self._emergency_handled: bool = False

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._intelligence_loop())
        logger.info("Traffic Intelligence Engine started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def update_direction_data(self, data: DirectionTrafficData):
        """
        Called by backend API when ML service sends traffic update.
        Thread-safe (asyncio single-threaded).
        """
        self.direction_data[data.direction] = data

        # Store history point
        self._history[data.direction].append({
            "timestamp": data.timestamp,
            "count": data.vehicle_count,
            "density_weight": data.density_weight,
            "queue_length": data.queue_length,
        })

        # Check for emergency (high priority — handle immediately)
        if data.emergency_detected:
            self._handle_emergency_detection(data)

        logger.debug(
            "Direction data updated",
            extra={
                "direction": data.direction.value,
                "count": data.vehicle_count,
                "density": data.density_level,
            }
        )

    def _handle_emergency_detection(self, data: DirectionTrafficData):
        """
        React to emergency detection from ML service.
        Stage 2 confirmed → trigger emergency override.
        Stage 2 unconfirmed → log, monitor, do NOT override yet.
        """
        if data.emergency_stage2_confirmed and not self._emergency_handled:
            logger.warning(
                f"EMERGENCY CONFIRMED: {data.emergency_type} at {data.direction.value} "
                f"(confidence={data.emergency_confidence:.2f})"
            )
            self._active_emergency_direction = data.direction
            self._emergency_handled = True

            # Schedule emergency override (non-blocking)
            asyncio.create_task(
                self.signal_controller.emergency_override(
                    data.direction,
                    data.emergency_type or "unknown"
                )
            )
        elif data.emergency_detected and not data.emergency_stage2_confirmed:
            logger.info(
                f"Emergency Stage 1 detected ({data.emergency_type}) at {data.direction.value} "
                f"— Stage 2 unconfirmed (confidence={data.emergency_confidence:.2f}). Monitoring."
            )

    async def _intelligence_loop(self):
        """Background loop: compute signal recommendations periodically."""
        while self._running:
            try:
                await asyncio.sleep(self.decision_interval)

                if self.signal_controller.emergency_active:
                    continue  # Emergency handler is in control

                if self.signal_controller.current_mode.value == "MANUAL":
                    continue  # Manual mode — don't interfere

                recommendation = self._compute_recommendation()
                if recommendation:
                    self.signal_controller.accept_recommendation(recommendation)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Intelligence loop error: {e}")

    def _compute_recommendation(self) -> Optional[SignalRecommendation]:
        """
        Compute optimal signal pair and duration based on current traffic data.
        Returns None if no data or no change needed.
        """
        # Score each compatible pair
        pair_scores = {}
        for pair in COMPATIBLE_PAIRS:
            total_score = 0.0
            total_count = 0
            worst_density = DensityLevel.LOW
            any_jam = False

            for d in pair:
                data = self.direction_data[d]
                if data.is_stale:
                    continue
                score = data.priority_score
                # Boost by prediction
                predicted_boost = self._get_prediction_boost(d)
                total_score += score * (1 + predicted_boost * 0.2)
                total_count += data.vehicle_count
                if DENSITY_WEIGHTS.get(data.density_level, 0) > DENSITY_WEIGHTS.get(worst_density, 0):
                    worst_density = data.density_level
                if data.density_level == DensityLevel.TRAFFIC_JAM:
                    any_jam = True

            pair_scores[pair] = {
                "score": total_score,
                "count": total_count,
                "density": worst_density,
                "has_jam": any_jam,
            }

        if not pair_scores:
            return None

        # Select highest-scoring pair
        best_pair = max(pair_scores, key=lambda p: pair_scores[p]["score"])
        best_info = pair_scores[best_pair]

        # Compute green duration from density
        density = best_info["density"]
        green_duration = float(self.GREEN_TIME_TABLE.get(density, 30))
        green_duration = self.signal_controller._clamp_duration(green_duration)

        # Build explanation
        dirs = [d.value for d in best_pair]
        primary_metrics = {}
        reason_parts = []

        for d in best_pair:
            data = self.direction_data[d]
            if not data.is_stale:
                primary_metrics = {
                    "vehicle_count": data.vehicle_count,
                    "density": data.density_level,
                    "queue_length": round(data.queue_length, 1),
                    "congestion_predicted": data.congestion_predicted,
                }
                if data.density_level in (DensityLevel.HIGH, DensityLevel.TRAFFIC_JAM):
                    reason_parts.append(f"traffic density is {data.density_level}")
                if data.queue_length > 60:
                    reason_parts.append("queue length is elevated")
                if data.congestion_predicted:
                    reason_parts.append("congestion is predicted to increase")
                if data.vehicle_count > 20:
                    reason_parts.append(f"vehicle count is high ({data.vehicle_count})")
                break

        if not reason_parts:
            reason_parts.append("it has the highest traffic priority score")

        reason_text = ", ".join(reason_parts)

        self.last_explanation = AIDecisionExplanation(
            selected_pair=dirs,
            primary_reason=reason_text,
            metrics=primary_metrics,
        )

        logger.info(
            f"Signal recommendation: {dirs} for {green_duration}s — {reason_text}"
        )

        return SignalRecommendation(
            active_pair=best_pair,
            green_duration=green_duration,
            reason=reason_text,
        )

    def _get_prediction_boost(self, direction: Direction) -> float:
        """
        Exponential smoothing prediction.
        Returns boost factor 0–1 based on predicted increase in traffic.
        """
        history = list(self._history[direction])
        if len(history) < 3:
            return 0.0

        # Exponential smoothing
        alpha = 0.3
        smoothed = history[0]["count"]
        for point in history[1:]:
            smoothed = alpha * point["count"] + (1 - alpha) * smoothed

        current = history[-1]["count"]
        if current <= 0:
            return 0.0

        # If smoothed (predicted) is higher than current, boost this direction
        boost = max(0.0, (smoothed - current) / max(current, 1))
        return min(boost, 1.0)

    def get_all_traffic_data(self) -> dict:
        """Return all direction data as dict for API."""
        return {
            d.value: {
                "vehicle_count": self.direction_data[d].vehicle_count,
                "density_level": self.direction_data[d].density_level,
                "speed_estimate": self.direction_data[d].speed_estimate,
                "speed_is_estimate": self.direction_data[d].speed_is_estimate,
                "queue_length": self.direction_data[d].queue_length,
                "congestion_predicted": self.direction_data[d].congestion_predicted,
                "emergency_detected": self.direction_data[d].emergency_detected,
                "emergency_type": self.direction_data[d].emergency_type,
                "emergency_stage2_confirmed": self.direction_data[d].emergency_stage2_confirmed,
                "emergency_confidence": self.direction_data[d].emergency_confidence,
                "is_stale": self.direction_data[d].is_stale,
                "timestamp": self.direction_data[d].timestamp,
            }
            for d in Direction
        }

    def get_ai_explanation(self) -> Optional[dict]:
        """Return the latest AI decision explanation."""
        if not self.last_explanation:
            return None
        return {
            "selected_pair": self.last_explanation.selected_pair,
            "explanation_text": self.last_explanation.to_text(),
            "primary_reason": self.last_explanation.primary_reason,
            "metrics": self.last_explanation.metrics,
            "timestamp": self.last_explanation.timestamp,
            "is_emergency": self.last_explanation.is_emergency,
        }
