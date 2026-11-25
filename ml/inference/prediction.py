"""
ml/inference/prediction.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
Lightweight 30-60 second traffic prediction module.
Compares Moving Average, Exponential Smoothing, Random Forest, and Gradient Boosting
on rolling validation windows and selects the lowest-RMSE predictor.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor

from .density_analyzer import DensityLevel


@dataclass
class PredictionResult:
    direction: str
    expected_vehicle_count: int
    expected_congestion_level: DensityLevel
    possible_traffic_jam: bool
    recommended_green_seconds: int
    selected_model: str
    validation_rmse: Optional[float]
    horizon_seconds: int
    timestamp: float = field(default_factory=time.time)


@dataclass
class SignalRecommendation:
    active_pair: tuple[str, str]
    recommended_green: int
    reason: str
    predictions: Dict[str, PredictionResult]


class TrafficPredictor:
    """
    Compares lightweight forecasting methods on recent traffic history:
      - moving_average
      - exponential_smoothing
      - random_forest
      - gradient_boosting
    """

    def __init__(self, method: str = "auto", horizon_seconds: int = 45, rebenchmark_interval: float = 5.0) -> None:
        self.preferred_method = method
        self.horizon_seconds = horizon_seconds
        self.rebenchmark_interval = rebenchmark_interval
        self.history: Dict[str, deque] = {
            d: deque(maxlen=120) for d in ("north", "south", "east", "west")
        }
        self.model_scores: Dict[str, float] = {}
        self._last_benchmark_at: Dict[str, float] = {}
        self._cached_model: Dict[str, tuple[str, Optional[float], object | None]] = {}

    def update(self, direction: str, count: int, density: str, timestamp: Optional[float] = None) -> None:
        ts = timestamp or time.time()
        if direction not in self.history:
            self.history[direction] = deque(maxlen=120)
        self.history[direction].append((ts, float(count), density))

    @staticmethod
    def _moving_average(values: np.ndarray, k: int = 5) -> float:
        return float(np.mean(values[-min(k, len(values)):]))

    @staticmethod
    def _exponential_smoothing(values: np.ndarray, alpha: float = 0.35) -> float:
        level = float(values[0])
        for v in values[1:]:
            level = alpha * float(v) + (1.0 - alpha) * level
        return level

    @staticmethod
    def _ml_regressor(values: np.ndarray, model_type: str) -> float:
        lags = 5
        if len(values) <= lags + 3:
            return float(values[-1])
        X, y = [], []
        for i in range(lags, len(values)):
            X.append(values[i - lags:i])
            y.append(values[i])
        X_arr, y_arr = np.array(X), np.array(y)
        if model_type == "random_forest":
            reg = RandomForestRegressor(n_estimators=20, max_depth=4, random_state=42)
        else:
            reg = GradientBoostingRegressor(n_estimators=25, max_depth=3, learning_rate=0.1, random_state=42)
        reg.fit(X_arr, y_arr)
        return float(reg.predict(values[-lags:].reshape(1, -1))[0])

    def _benchmark_methods(self, values: np.ndarray) -> tuple[str, float, Optional[float]]:
        """Evaluate candidate predictors via one-step-ahead walk-forward RMSE."""
        if len(values) < 12:
            pred = self._exponential_smoothing(values)
            return "exponential_smoothing", pred, None

        split = max(6, len(values) - 5)
        train_vals = values[:split]
        test_vals = values[split:]

        candidates: Dict[str, List[float]] = {
            "moving_average": [],
            "exponential_smoothing": [],
            "random_forest": [],
            "gradient_boosting": [],
        }

        for i in range(len(test_vals)):
            prefix = np.concatenate([train_vals, test_vals[:i]])
            candidates["moving_average"].append(self._moving_average(prefix))
            candidates["exponential_smoothing"].append(self._exponential_smoothing(prefix))
            candidates["random_forest"].append(self._ml_regressor(prefix, "random_forest"))
            candidates["gradient_boosting"].append(self._ml_regressor(prefix, "gradient_boosting"))

        rmses: Dict[str, float] = {}
        for name, preds in candidates.items():
            rmses[name] = float(np.sqrt(np.mean((np.array(preds) - test_vals) ** 2)))

        self.model_scores = rmses
        best_name = min(rmses, key=rmses.get)  # type: ignore[arg-type]

        if best_name == "moving_average":
            next_val = self._moving_average(values)
        elif best_name == "exponential_smoothing":
            next_val = self._exponential_smoothing(values)
        else:
            next_val = self._ml_regressor(values, best_name)

        return best_name, max(0.0, next_val), round(rmses[best_name], 3)

    @staticmethod
    def _count_to_density(count: int) -> DensityLevel:
        if count <= 5:
            return DensityLevel.LOW
        if count <= 15:
            return DensityLevel.NORMAL
        if count <= 25:
            return DensityLevel.MEDIUM
        if count <= 40:
            return DensityLevel.HIGH
        return DensityLevel.TRAFFIC_JAM

    def predict(self, direction: str, horizon_seconds: Optional[int] = None) -> PredictionResult:
        horizon = horizon_seconds or self.horizon_seconds
        pts = list(self.history.get(direction, []))
        if not pts:
            return PredictionResult(
                direction=direction,
                expected_vehicle_count=0,
                expected_congestion_level=DensityLevel.LOW,
                possible_traffic_jam=False,
                recommended_green_seconds=20,
                selected_model="insufficient_history",
                validation_rmse=None,
                horizon_seconds=horizon,
            )

        values = np.array([p[1] for p in pts], dtype=float)
        if self.preferred_method == "moving_average":
            model_name, pred_float, rmse = "moving_average", self._moving_average(values), None
        elif self.preferred_method == "exponential_smoothing":
            model_name, pred_float, rmse = "exponential_smoothing", self._exponential_smoothing(values), None
        else:
            now = time.monotonic()
            last_bench = self._last_benchmark_at.get(direction, 0.0)
            cached = self._cached_model.get(direction)
            if cached is None or len(values) < 12 or (now - last_bench) >= self.rebenchmark_interval:
                model_name, pred_float, rmse = self._benchmark_methods(values)
                if len(values) >= 12:
                    self._last_benchmark_at[direction] = now
                    fitted = None
                    if model_name in ("random_forest", "gradient_boosting") and len(values) > 8:
                        lags = 5
                        X_arr = np.array([values[i - lags:i] for i in range(lags, len(values))])
                        y_arr = np.array([values[i] for i in range(lags, len(values))])
                        fitted = (
                            RandomForestRegressor(n_estimators=20, max_depth=4, random_state=42)
                            if model_name == "random_forest"
                            else GradientBoostingRegressor(n_estimators=25, max_depth=3, learning_rate=0.1, random_state=42)
                        )
                        fitted.fit(X_arr, y_arr)
                    self._cached_model[direction] = (model_name, rmse, fitted)
            else:
                model_name, rmse, fitted = cached
                if model_name == "moving_average":
                    pred_float = self._moving_average(values)
                elif model_name == "exponential_smoothing" or fitted is None:
                    pred_float = self._exponential_smoothing(values)
                else:
                    pred_float = max(0.0, float(fitted.predict(values[-5:].reshape(1, -1))[0]))

        expected_count = max(0, int(round(pred_float)))
        expected_level = self._count_to_density(expected_count)
        jam_possible = expected_level in (DensityLevel.HIGH, DensityLevel.TRAFFIC_JAM)

        green_map = {
            DensityLevel.LOW: 20,
            DensityLevel.NORMAL: 30,
            DensityLevel.MEDIUM: 50,
            DensityLevel.HIGH: 80,
            DensityLevel.TRAFFIC_JAM: 110,
        }
        return PredictionResult(
            direction=direction,
            expected_vehicle_count=expected_count,
            expected_congestion_level=expected_level,
            possible_traffic_jam=jam_possible,
            recommended_green_seconds=green_map[expected_level],
            selected_model=model_name,
            validation_rmse=rmse,
            horizon_seconds=horizon,
        )

    def recommend_signal_timing(self) -> SignalRecommendation:
        preds = {d: self.predict(d) for d in ("north", "south", "east", "west")}
        ns_load = preds["north"].expected_vehicle_count + preds["south"].expected_vehicle_count
        ew_load = preds["east"].expected_vehicle_count + preds["west"].expected_vehicle_count
        if ns_load >= ew_load:
            pair = ("north", "south")
            rec = max(preds["north"].recommended_green_seconds, preds["south"].recommended_green_seconds)
            reason = f"Predicted N+S load ({ns_load}) >= E+W load ({ew_load})"
        else:
            pair = ("east", "west")
            rec = max(preds["east"].recommended_green_seconds, preds["west"].recommended_green_seconds)
            reason = f"Predicted E+W load ({ew_load}) > N+S load ({ns_load})"

        return SignalRecommendation(
            active_pair=pair,
            recommended_green=rec,
            reason=reason,
            predictions=preds,
        )
