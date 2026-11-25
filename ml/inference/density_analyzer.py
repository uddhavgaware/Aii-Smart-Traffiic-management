"""
ml/inference/density_analyzer.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Analyzes traffic density from tracked vehicles.

Density classification uses a weighted combination of:
  1. Vehicle count in ROI
  2. Estimated queue length (slow/stationary vehicles)
  3. Relative speed estimate (centroid displacement between frames)
  4. ROI coverage (fraction of ROI occupied by vehicle bounding boxes)

Density levels: LOW → NORMAL → MEDIUM → HIGH → TRAFFIC_JAM

Speed values are ALWAYS labeled as estimates when the camera is uncalibrated.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import cv2
import numpy as np

from .tracker import TrackedVehicle, TrackerResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data-classes
# ---------------------------------------------------------------------------

class DensityLevel(str, Enum):
    LOW         = "LOW"
    NORMAL      = "NORMAL"
    MEDIUM      = "MEDIUM"
    HIGH        = "HIGH"
    TRAFFIC_JAM = "TRAFFIC_JAM"


@dataclass
class SpeedEstimate:
    """Relative speed (pixels/frame or km/h if calibrated)."""
    value: float                 # numeric value
    unit: str = "px/frame"      # "px/frame" or "km/h"
    is_estimate: bool = True    # always True when uncalibrated
    label: str = "ESTIMATE – uncalibrated"

    def __post_init__(self):
        if self.is_estimate:
            self.label = f"ESTIMATE – uncalibrated ({self.value:.1f} {self.unit})"


@dataclass
class DensityResult:
    """Traffic density analysis result for one frame."""
    level: DensityLevel = DensityLevel.LOW
    vehicle_count: int = 0
    queue_length: float = 0.0        # estimated # of stopped vehicles
    roi_coverage: float = 0.0        # 0.0–1.0
    speed_estimate: Optional[SpeedEstimate] = None
    weighted_score: float = 0.0
    timestamp: float = field(default_factory=time.time)

    @property
    def is_congested(self) -> bool:
        return self.level in (DensityLevel.HIGH, DensityLevel.TRAFFIC_JAM)


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class TrafficDensityAnalyzer:
    """
    Analyzes traffic density from ByteTrack results.

    Parameters
    ----------
    config : dict
        Density subsection of model_config.yaml.
    calibrated : bool
        Whether camera is geometrically calibrated.  When False all speed
        values are labelled as estimates.
    """

    _LEVEL_ORDER = [
        DensityLevel.LOW,
        DensityLevel.NORMAL,
        DensityLevel.MEDIUM,
        DensityLevel.HIGH,
        DensityLevel.TRAFFIC_JAM,
    ]

    def __init__(self, config: dict, calibrated: bool = False) -> None:
        self._cfg = config
        self._calibrated = calibrated

        thresholds = config.get("thresholds", {})
        self._thresholds: list[tuple[int, DensityLevel]] = [
            (int(thresholds.get("low", 5)),    DensityLevel.LOW),
            (int(thresholds.get("normal", 15)), DensityLevel.NORMAL),
            (int(thresholds.get("medium", 25)), DensityLevel.MEDIUM),
            (int(thresholds.get("high", 40)),   DensityLevel.HIGH),
            (int(thresholds.get("jam", 999)),   DensityLevel.TRAFFIC_JAM),
        ]

        self._roi_w: float  = float(config.get("roi_coverage_weight", 0.3))
        self._queue_w: float = float(config.get("queue_weight", 0.4))
        self._speed_w: float = float(config.get("speed_weight", 0.3))

        # History for speed estimation (track_id → deque of centroids)
        self._centroid_history: dict[int, deque] = {}
        self._frame_buffer: deque[np.ndarray] = deque(maxlen=5)

        # Optical-flow state
        self._prev_gray: Optional[np.ndarray] = None
        self._lk_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _classify_by_count(self, count: int) -> DensityLevel:
        for threshold, level in self._thresholds:
            if count <= threshold:
                return level
        return DensityLevel.TRAFFIC_JAM

    def _roi_area(self, roi_polygon: np.ndarray) -> float:
        return float(cv2.contourArea(roi_polygon.astype(np.float32)))

    def _point_in_roi(self, point: np.ndarray, roi_polygon: np.ndarray) -> bool:
        """Check if a 2D point is inside the ROI polygon."""
        result = cv2.pointPolygonTest(
            roi_polygon.astype(np.float32),
            (float(point[0]), float(point[1])),
            measureDist=False,
        )
        return result >= 0

    def _bbox_area(self, bbox: np.ndarray) -> float:
        return float((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        tracks: TrackerResult,
        roi_polygon: np.ndarray,
        frame: Optional[np.ndarray] = None,
    ) -> DensityResult:
        """
        Compute density for one frame.

        Parameters
        ----------
        tracks : TrackerResult
            Output from VehicleTracker.update().
        roi_polygon : np.ndarray
            Polygon in pixel coords defining the region of interest, shape (N, 2).
        frame : np.ndarray | None
            Current BGR frame; used for optical-flow speed estimation.
        """
        # --- Filter tracks inside ROI ---
        in_roi: list[TrackedVehicle] = [
            t for t in tracks.tracks
            if self._point_in_roi(t.centroid, roi_polygon)
        ]
        count = len(in_roi)

        # --- Queue length ---
        queue_len = self.estimate_queue_length(tracks, roi_polygon)

        # --- Speed estimate ---
        speed_est = self.estimate_relative_speed(tracks, frame)

        # --- ROI coverage ---
        roi_area = max(self._roi_area(roi_polygon), 1.0)
        bbox_union_area = sum(self._bbox_area(t.bbox_xyxy) for t in in_roi)
        roi_coverage = min(bbox_union_area / roi_area, 1.0)

        # --- Weighted density score (normalized per component) ---
        count_norm   = min(count / 40.0, 1.0)              # 40 = jam threshold
        queue_norm   = min(queue_len / 20.0, 1.0)          # 20 stopped = jam
        roi_cov_norm = roi_coverage                         # already 0–1

        # Speed: low speed → higher score (inverted)
        speed_norm = 0.0
        if speed_est is not None and speed_est.value >= 0:
            # value in px/frame; 0 = stopped, >15 = fast → normalize inverted
            speed_norm = max(0.0, 1.0 - (speed_est.value / 15.0))

        weighted = (
            self._roi_w  * roi_cov_norm +
            self._queue_w * queue_norm +
            self._speed_w * speed_norm
        )

        # --- Blend count-based and weighted-score-based classification ---
        count_level = self._classify_by_count(count)
        # Convert weighted score to level index
        weighted_idx = min(int(weighted * len(self._LEVEL_ORDER)), len(self._LEVEL_ORDER) - 1)
        count_idx    = self._LEVEL_ORDER.index(count_level)
        # Take the more severe of the two
        final_idx    = max(count_idx, weighted_idx)
        final_level  = self._LEVEL_ORDER[final_idx]

        # Update centroid history for next frame speed estimate
        if frame is not None:
            self._frame_buffer.append(frame)

        return DensityResult(
            level=final_level,
            vehicle_count=count,
            queue_length=queue_len,
            roi_coverage=roi_coverage,
            speed_estimate=speed_est,
            weighted_score=weighted,
        )

    def estimate_queue_length(
        self,
        tracks: TrackerResult,
        roi_polygon: np.ndarray,
        speed_threshold_px: float = 2.0,
    ) -> float:
        """
        Estimate the number of stationary or near-stationary vehicles.

        A vehicle is considered 'queued' if its centroid displacement between
        the last two frames is below speed_threshold_px pixels.
        """
        queue = 0
        for t in tracks.tracks:
            if not self._point_in_roi(t.centroid, roi_polygon):
                continue
            tid = t.track_id
            history = self._centroid_history.get(tid, deque(maxlen=5))
            if len(history) >= 2:
                displacement = float(np.linalg.norm(
                    np.array(history[-1]) - np.array(history[-2])
                ))
                if displacement < speed_threshold_px:
                    queue += 1
            # Store current centroid
            history.append(t.centroid.tolist())
            self._centroid_history[tid] = history

        # Clean up stale track histories
        active_ids = {t.track_id for t in tracks.tracks}
        stale = set(self._centroid_history.keys()) - active_ids
        for sid in stale:
            del self._centroid_history[sid]

        return float(queue)

    def estimate_relative_speed(
        self,
        tracks: TrackerResult,
        frame: Optional[np.ndarray] = None,
    ) -> Optional[SpeedEstimate]:
        """
        Estimate average relative vehicle speed using centroid displacement.

        When a grayscale frame is available, falls back to sparse Lucas-Kanade
        optical flow for a more stable estimate on camera shake.

        Returns
        -------
        SpeedEstimate
            Always labelled as estimate when camera is uncalibrated.
        """
        if not tracks.tracks:
            return None

        displacements: list[float] = []
        for t in tracks.tracks:
            tid = t.track_id
            history = self._centroid_history.get(tid)
            if history and len(history) >= 2:
                d = float(np.linalg.norm(
                    np.array(history[-1]) - np.array(history[-2])
                ))
                displacements.append(d)

        if not displacements:
            return SpeedEstimate(value=0.0, is_estimate=not self._calibrated)

        avg_displacement = float(np.mean(displacements))

        # Optional: supplement with optical flow on frame
        if frame is not None and self._prev_gray is not None:
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                # Build feature points from track centroids
                pts = np.array(
                    [[t.centroid[0], t.centroid[1]] for t in tracks.tracks],
                    dtype=np.float32,
                ).reshape(-1, 1, 2)
                if len(pts) >= 1:
                    new_pts, status, _ = cv2.calcOpticalFlowPyrLK(
                        self._prev_gray, gray, pts, None, **self._lk_params
                    )
                    good = status.ravel() == 1
                    if good.any():
                        flow_mags = np.linalg.norm(
                            (new_pts[good] - pts[good]).reshape(-1, 2), axis=1
                        )
                        avg_displacement = float(np.mean(flow_mags))
                self._prev_gray = gray
            except Exception:  # noqa: BLE001
                pass
        elif frame is not None:
            try:
                self._prev_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            except Exception:  # noqa: BLE001
                pass

        return SpeedEstimate(
            value=avg_displacement,
            unit="px/frame",
            is_estimate=not self._calibrated,
        )
