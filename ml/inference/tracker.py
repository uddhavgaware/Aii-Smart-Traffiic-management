"""
ml/inference/tracker.py
~~~~~~~~~~~~~~~~~~~~~~~
ByteTrack-based vehicle tracker using the `supervision` library.

Responsibilities:
  - Assign stable track IDs across frames.
  - Count vehicles that cross a user-defined reference line.
  - Prevent duplicate counting per track ID.
  - Return structured TrackerResult objects.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import supervision as sv

from .model import Detection, DetectionResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data-classes
# ---------------------------------------------------------------------------

@dataclass
class TrackedVehicle:
    """A single vehicle track at a given frame."""
    track_id: int
    bbox_xyxy: np.ndarray          # [x1, y1, x2, y2]
    centroid: np.ndarray           # [cx, cy]
    class_id: int
    class_name: str
    confidence: float
    is_emergency: bool
    frames_seen: int = 1


@dataclass
class TrackerResult:
    """All active tracks for a single frame."""
    tracks: list[TrackedVehicle] = field(default_factory=list)
    crossing_counts: dict[str, int] = field(default_factory=dict)  # class_name → count
    total_crossings: int = 0
    frame_shape: tuple[int, int, int] = (0, 0, 3)
    timestamp: float = field(default_factory=time.time)

    @property
    def num_active(self) -> int:
        return len(self.tracks)

    @property
    def emergency_tracks(self) -> list[TrackedVehicle]:
        return [t for t in self.tracks if t.is_emergency]


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------

class VehicleTracker:
    """
    Tracks vehicles across video frames using ByteTrack (via supervision).

    Parameters
    ----------
    config : dict
        Tracking subsection of model_config.yaml::

            tracking:
              max_age: 30
              min_hits: 3
              iou_threshold: 0.3

    reference_line : optional tuple
        ((x1, y1), (x2, y2)) in pixel coords.  Vehicles whose centroid
        crosses this line from top→bottom (or left→right) are counted.
        Pass None to disable line crossing counting.
    """

    def __init__(
        self,
        config: dict,
        reference_line: Optional[tuple[tuple[int, int], tuple[int, int]]] = None,
    ) -> None:
        self._cfg = config
        self._reference_line = reference_line

        self._tracker = sv.ByteTrack(
            track_activation_threshold=float(config.get("activation_threshold", 0.25)),
            lost_track_buffer=int(config.get("max_age", 30)),
            minimum_matching_threshold=float(config.get("match_threshold", 0.8)),
            frame_rate=int(config.get("frame_rate", 5)),
            minimum_consecutive_frames=int(config.get("min_hits", 3)),
        )

        # State for line-crossing counting
        self._prev_centroids: dict[int, np.ndarray] = {}   # track_id → centroid
        self._counted_ids: set[int] = set()                 # prevent double-count
        self._crossing_counts: dict[str, int] = {}          # class_name → n

        # Map track_id → (class_id, class_name, is_emergency)
        self._track_meta: dict[int, tuple[int, str, bool]] = {}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _centroid(bbox: np.ndarray) -> np.ndarray:
        return np.array([(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2])

    def _build_sv_detections(self, result: DetectionResult) -> sv.Detections:
        """Convert DetectionResult → supervision Detections."""
        if not result.detections:
            return sv.Detections.empty()

        boxes  = np.array([d.bbox_xyxy for d in result.detections], dtype=np.float32)
        confs  = np.array([d.confidence for d in result.detections], dtype=np.float32)
        cls_ids = np.array([d.class_id for d in result.detections], dtype=int)

        return sv.Detections(
            xyxy=boxes,
            confidence=confs,
            class_id=cls_ids,
        )

    def _check_line_crossing(
        self,
        track_id: int,
        centroid: np.ndarray,
        class_name: str,
    ) -> None:
        """
        Detect if a track centroid crosses the reference line between this
        and the previous frame.  Uses a simple sign-of-cross-product check.
        """
        if self._reference_line is None:
            return
        if track_id in self._counted_ids:
            return
        if track_id not in self._prev_centroids:
            return

        p1 = np.array(self._reference_line[0], dtype=float)
        p2 = np.array(self._reference_line[1], dtype=float)
        line_vec = p2 - p1

        prev_c = self._prev_centroids[track_id]
        prev_side = np.cross(line_vec, prev_c - p1)
        curr_side = np.cross(line_vec, centroid - p1)

        if prev_side * curr_side < 0:  # sign changed → crossed
            self._counted_ids.add(track_id)
            self._crossing_counts[class_name] = (
                self._crossing_counts.get(class_name, 0) + 1
            )
            logger.debug("Vehicle %d (%s) crossed reference line.", track_id, class_name)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, detections: DetectionResult, frame: np.ndarray) -> TrackerResult:
        """
        Update tracker with new detections.

        Parameters
        ----------
        detections : DetectionResult
            Output from TrafficDetectionModel.detect().
        frame : np.ndarray
            Current frame (H×W×3 BGR).  Used for frame_shape metadata.

        Returns
        -------
        TrackerResult
        """
        sv_dets = self._build_sv_detections(detections)

        # Build a lookup for class info indexed by detection position
        det_meta: dict[int, tuple[int, str, bool]] = {}
        for i, d in enumerate(detections.detections):
            det_meta[i] = (d.class_id, d.class_name, d.is_emergency)

        # Update ByteTrack
        tracked_sv: sv.Detections = self._tracker.update_with_detections(sv_dets)

        tracks: list[TrackedVehicle] = []

        for i in range(len(tracked_sv)):
            tid  = int(tracked_sv.tracker_id[i])
            bbox = tracked_sv.xyxy[i]
            conf = float(tracked_sv.confidence[i]) if tracked_sv.confidence is not None else 0.0
            cls  = int(tracked_sv.class_id[i]) if tracked_sv.class_id is not None else -1

            # Recover meta from original detection list by class matching
            if tid not in self._track_meta:
                # Find matching detection by class id
                matched = next(
                    ((cid, cn, ie) for _, (cid, cn, ie) in det_meta.items() if cid == cls),
                    (cls, f"class_{cls}", cls in {5, 6}),
                )
                self._track_meta[tid] = matched

            cid, cname, is_em = self._track_meta[tid]
            centroid = self._centroid(bbox)

            self._check_line_crossing(tid, centroid, cname)
            self._prev_centroids[tid] = centroid

            tracks.append(TrackedVehicle(
                track_id=tid,
                bbox_xyxy=bbox,
                centroid=centroid,
                class_id=cid,
                class_name=cname,
                confidence=conf,
                is_emergency=is_em,
            ))

        return TrackerResult(
            tracks=tracks,
            crossing_counts=dict(self._crossing_counts),
            total_crossings=sum(self._crossing_counts.values()),
            frame_shape=frame.shape if frame is not None else (0, 0, 3),
        )

    def get_crossing_count(self) -> dict:
        """Return cumulative per-class vehicle counts that crossed the line."""
        return {
            "per_class": dict(self._crossing_counts),
            "total": sum(self._crossing_counts.values()),
            "counted_track_ids": len(self._counted_ids),
        }

    def reset_counts(self) -> None:
        """Reset crossing counts (e.g., at start of new signal cycle)."""
        self._crossing_counts.clear()
        self._counted_ids.clear()
        logger.info("Vehicle crossing counts reset.")

    def set_reference_line(
        self,
        line: Optional[tuple[tuple[int, int], tuple[int, int]]],
    ) -> None:
        """Update the reference counting line at runtime."""
        self._reference_line = line
        logger.info("Reference line updated: %s", line)
