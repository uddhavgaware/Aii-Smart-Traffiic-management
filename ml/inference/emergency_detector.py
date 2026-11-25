"""
ml/inference/emergency_detector.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Two-stage emergency vehicle detector.

Stage 1  – Vehicle class detection (ambulance / fire_brigade) from tracker.
Stage 2  – Emergency *activity* classification via temporal visual analysis:
           • Frame-difference analysis to detect flashing light patterns
           • Red/blue high-saturation color analysis in vehicle ROI
           • Temporal consistency: flashing must occur 2+ times in a window

Outputs:
  CONFIRMED   – confidence > 0.7
  UNCONFIRMED – 0.3 < confidence ≤ 0.7
  NORMAL      – confidence ≤ 0.3   (vehicle type only, not actively responding)

Uncertainty is ALWAYS surfaced; it is NEVER hidden or fabricated.
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

class EmergencyStatus(str, Enum):
    CONFIRMED   = "CONFIRMED"
    UNCONFIRMED = "UNCONFIRMED"
    NORMAL      = "NORMAL"


@dataclass
class EmergencyCandidate:
    """Stage 1 output — vehicle identified by class as potentially emergency."""
    track_id: int
    class_name: str
    bbox_xyxy: np.ndarray
    confidence: float   # detection confidence


@dataclass
class EmergencyClassification:
    """Stage 2 output — activity classification for one track."""
    track_id: int
    class_name: str
    bbox_xyxy: np.ndarray
    status: EmergencyStatus
    confidence: float                   # 0.0–1.0
    flash_count: int = 0
    color_match_score: float = 0.0
    uncertainty_note: str = ""

    def __post_init__(self):
        if self.status == EmergencyStatus.CONFIRMED:
            self.uncertainty_note = (
                f"Emergency lights detected with {self.confidence:.0%} confidence."
            )
        elif self.status == EmergencyStatus.UNCONFIRMED:
            self.uncertainty_note = (
                f"Possible emergency activity — uncertain ({self.confidence:.0%} confidence). "
                "Flashing pattern or color not fully confirmed."
            )
        else:
            self.uncertainty_note = (
                f"Vehicle type is {self.class_name} but no active emergency lights detected "
                f"(confidence {self.confidence:.0%})."
            )


@dataclass
class EmergencyState:
    """Combined state across all tracks for one frame."""
    active_emergencies: list[EmergencyClassification] = field(default_factory=list)
    has_confirmed: bool = False
    has_unconfirmed: bool = False
    timestamp: float = field(default_factory=time.time)

    @property
    def alert_level(self) -> str:
        if self.has_confirmed:
            return "HIGH"
        if self.has_unconfirmed:
            return "MEDIUM"
        return "NONE"


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class EmergencyDetector:
    """
    Two-stage emergency vehicle detector.

    Parameters
    ----------
    config : dict
        Detector config (from model_config.yaml or custom dict).
    history_len : int
        Number of frames to retain per track (default 30 ≈ 6 s at 5 FPS).
    confirm_threshold : float
        Minimum confidence to report CONFIRMED.
    uncertain_threshold : float
        Minimum confidence to report UNCONFIRMED.
    """

    EMERGENCY_CLASSES: frozenset[str] = frozenset({"ambulance", "fire_brigade"})

    def __init__(
        self,
        config: dict,
        history_len: int = 30,
        confirm_threshold: float = 0.70,
        uncertain_threshold: float = 0.30,
    ) -> None:
        self._cfg = config
        self._history_len = history_len
        self._confirm_thr = confirm_threshold
        self._uncertain_thr = uncertain_threshold

        # track_id → deque of (frame_roi, timestamp)
        self._roi_history: dict[int, deque] = {}
        # track_id → latest classification
        self._classification_cache: dict[int, EmergencyClassification] = {}

    # ------------------------------------------------------------------
    # Stage 1
    # ------------------------------------------------------------------

    def stage1_detect(self, tracks: TrackerResult) -> list[EmergencyCandidate]:
        """
        Filter tracker results for emergency-class vehicles.

        Returns a list of EmergencyCandidate — this does NOT yet mean they are
        actively responding.  Stage 2 is needed to classify activity.
        """
        candidates: list[EmergencyCandidate] = []
        for t in tracks.tracks:
            if t.class_name in self.EMERGENCY_CLASSES:
                candidates.append(EmergencyCandidate(
                    track_id=t.track_id,
                    class_name=t.class_name,
                    bbox_xyxy=t.bbox_xyxy.copy(),
                    confidence=t.confidence,
                ))
        return candidates

    # ------------------------------------------------------------------
    # Stage 2
    # ------------------------------------------------------------------

    def _extract_roi(
        self, frame: np.ndarray, bbox: np.ndarray
    ) -> Optional[np.ndarray]:
        """Crop and return vehicle ROI from frame; None if invalid."""
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = (
            max(0, int(bbox[0])), max(0, int(bbox[1])),
            min(w, int(bbox[2])), min(h, int(bbox[3])),
        )
        if x2 <= x1 or y2 <= y1:
            return None
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            return None
        return roi

    def _detect_flashing(self, roi_history: deque) -> tuple[int, float]:
        """
        Analyze frame-to-frame ROI differences for alternating bright regions.

        Returns
        -------
        (flash_count, flash_confidence)
        """
        rois = [item[0] for item in roi_history]
        if len(rois) < 4:
            return 0, 0.0

        # Compute per-frame mean luminance in a small center crop
        luminances: list[float] = []
        for roi in rois:
            try:
                gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                # Focus on a 50% center crop to avoid background noise
                cy, cx = gray.shape[0] // 2, gray.shape[1] // 2
                crop_h = max(gray.shape[0] // 4, 1)
                crop_w = max(gray.shape[1] // 4, 1)
                center = gray[
                    max(0, cy - crop_h):cy + crop_h,
                    max(0, cx - crop_w):cx + crop_w,
                ]
                luminances.append(float(np.mean(center)))
            except Exception:  # noqa: BLE001
                luminances.append(0.0)

        if len(luminances) < 4:
            return 0, 0.0

        # Count alternating high-low-high-low transitions
        threshold = np.std(luminances) * 1.0  # adaptive threshold
        flash_count = 0
        prev_state = None
        for lum in luminances:
            if threshold < 1.0:
                break
            state = "bright" if lum > np.mean(luminances) + threshold * 0.3 else "dim"
            if prev_state and state != prev_state:
                flash_count += 1
            prev_state = state

        # Expected: 1 flash per second → history_len / fps / 2 cycles
        expected_flashes = max(1, len(rois) // 4)
        confidence = min(1.0, flash_count / expected_flashes)
        return flash_count, confidence

    def _detect_emergency_colors(self, roi_history: deque) -> float:
        """
        Look for red/blue high-saturation regions across ROI frames.

        Returns a color_match_score in [0, 1].
        """
        if not roi_history:
            return 0.0

        color_scores: list[float] = []
        for roi, _ in roi_history:
            try:
                hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                total_px = hsv.shape[0] * hsv.shape[1]
                if total_px == 0:
                    continue

                # Red hue: 0-10 and 160-180 (wraps around), high sat, high val
                red_mask1 = cv2.inRange(hsv, (0, 120, 100), (10, 255, 255))
                red_mask2 = cv2.inRange(hsv, (160, 120, 100), (180, 255, 255))
                red_mask  = cv2.bitwise_or(red_mask1, red_mask2)

                # Blue hue: 100–130
                blue_mask = cv2.inRange(hsv, (100, 120, 100), (130, 255, 255))

                emergency_px = int(np.count_nonzero(red_mask)) + int(np.count_nonzero(blue_mask))
                color_scores.append(min(1.0, emergency_px / (total_px * 0.15)))
            except Exception:  # noqa: BLE001
                pass

        return float(np.mean(color_scores)) if color_scores else 0.0

    def stage2_classify(
        self,
        track_id: int,
        class_name: str,
        frame: np.ndarray,
        bbox: np.ndarray,
    ) -> EmergencyClassification:
        """
        Classify whether an emergency-class vehicle is actively responding.

        Parameters
        ----------
        track_id : int
        class_name : str
        frame : np.ndarray  BGR frame
        bbox : np.ndarray   [x1, y1, x2, y2]

        Returns
        -------
        EmergencyClassification  with status CONFIRMED / UNCONFIRMED / NORMAL
        """
        # --- Accumulate ROI history ---
        roi = self._extract_roi(frame, bbox)
        if track_id not in self._roi_history:
            self._roi_history[track_id] = deque(maxlen=self._history_len)
        if roi is not None:
            self._roi_history[track_id].append((roi, time.time()))

        history = self._roi_history[track_id]

        # Need at least a few frames for meaningful analysis
        if len(history) < 4:
            clf = EmergencyClassification(
                track_id=track_id,
                class_name=class_name,
                bbox_xyxy=bbox,
                status=EmergencyStatus.UNCONFIRMED,
                confidence=0.0,
                uncertainty_note=(
                    "Insufficient frame history for emergency light analysis "
                    f"({len(history)}/4 frames seen)."
                ),
            )
            self._classification_cache[track_id] = clf
            return clf

        # --- Run analysis ---
        flash_count, flash_conf = self._detect_flashing(history)
        color_score = self._detect_emergency_colors(history)

        # Combined confidence
        confidence = (flash_conf * 0.6) + (color_score * 0.4)
        # Require at least 2 flashing events
        if flash_count < 2:
            confidence *= 0.5   # penalise single-flash or no-flash

        # --- Classify ---
        if confidence > self._confirm_thr:
            status = EmergencyStatus.CONFIRMED
        elif confidence > self._uncertain_thr:
            status = EmergencyStatus.UNCONFIRMED
        else:
            status = EmergencyStatus.NORMAL

        clf = EmergencyClassification(
            track_id=track_id,
            class_name=class_name,
            bbox_xyxy=bbox,
            status=status,
            confidence=confidence,
            flash_count=flash_count,
            color_match_score=color_score,
        )
        self._classification_cache[track_id] = clf
        logger.debug(
            "Emergency Stage2 track=%d class=%s status=%s conf=%.2f flash=%d color=%.2f",
            track_id, class_name, status.value, confidence, flash_count, color_score,
        )
        return clf

    # ------------------------------------------------------------------
    # Combined pipeline
    # ------------------------------------------------------------------

    def process(
        self, tracks: TrackerResult, frame: np.ndarray
    ) -> EmergencyState:
        """
        Run both stages and return the combined EmergencyState.

        Call once per frame after VehicleTracker.update().
        """
        candidates = self.stage1_detect(tracks)
        active_emergencies: list[EmergencyClassification] = []

        for c in candidates:
            clf = self.stage2_classify(c.track_id, c.class_name, frame, c.bbox_xyxy)
            if clf.status != EmergencyStatus.NORMAL:
                active_emergencies.append(clf)

        # Expire histories for tracks no longer active
        active_ids = {t.track_id for t in tracks.tracks}
        stale = set(self._roi_history.keys()) - active_ids
        for sid in stale:
            del self._roi_history[sid]
            self._classification_cache.pop(sid, None)

        return EmergencyState(
            active_emergencies=active_emergencies,
            has_confirmed=any(e.status == EmergencyStatus.CONFIRMED for e in active_emergencies),
            has_unconfirmed=any(e.status == EmergencyStatus.UNCONFIRMED for e in active_emergencies),
        )

    def get_emergency_state(self) -> EmergencyState:
        """Return the most recently computed emergency state."""
        active = [
            clf for clf in self._classification_cache.values()
            if clf.status != EmergencyStatus.NORMAL
        ]
        return EmergencyState(
            active_emergencies=active,
            has_confirmed=any(e.status == EmergencyStatus.CONFIRMED for e in active),
            has_unconfirmed=any(e.status == EmergencyStatus.UNCONFIRMED for e in active),
        )
