"""
ml/inference/visualizer.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
Draws bounding boxes, track IDs, class labels, ROI polygon, queue HUD,
and emergency highlights onto video frames.
"""

from __future__ import annotations

import cv2
import numpy as np

from .density_analyzer import DensityResult
from .emergency_detector import EmergencyState, EmergencyStatus
from .tracker import TrackerResult

CLASS_BGR = {
    "car": (238, 211, 34),
    "motorcycle": (153, 211, 52),
    "bus": (250, 139, 167),
    "truck": (36, 191, 251),
    "auto_rickshaw": (182, 114, 244),
    "ambulance": (68, 68, 239),
    "fire_brigade": (68, 68, 239),
}


def annotate_frame(
    frame: np.ndarray,
    tracker_result: TrackerResult,
    density_result: DensityResult,
    emergency_state: EmergencyState,
    roi_polygon: np.ndarray | None = None,
    direction: str = "",
) -> np.ndarray:
    annotated = frame.copy()

    if roi_polygon is not None and len(roi_polygon) >= 3:
        cv2.polylines(annotated, [roi_polygon.astype(np.int32)], True, (238, 211, 34), 1)

    em_lookup = {e.track_id: e for e in emergency_state.active_emergencies}

    for tr in tracker_result.tracks:
        x1, y1, x2, y2 = [int(v) for v in tr.bbox_xyxy]
        em_clf = em_lookup.get(tr.track_id)
        is_confirmed = em_clf is not None and em_clf.status == EmergencyStatus.CONFIRMED
        color = (0, 0, 255) if (tr.is_emergency or is_confirmed) else CLASS_BGR.get(tr.class_name, (238, 211, 34))
        thickness = 3 if tr.is_emergency else 2

        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)
        label = f"{tr.class_name} #{tr.track_id} {tr.confidence:.0%}"
        if em_clf is not None:
            label += f" [{em_clf.status.value}]"
        cv2.putText(
            annotated,
            label,
            (x1, max(16, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            color,
            1,
            cv2.LINE_AA,
        )

    hud = f"{direction.upper()} | Count: {density_result.vehicle_count} | {density_result.level.value} | Q: {density_result.queue_length:.0f}"
    cv2.rectangle(annotated, (6, 6), (min(annotated.shape[1] - 6, 480), 32), (15, 23, 42), -1)
    cv2.putText(annotated, hud, (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (241, 245, 249), 1, cv2.LINE_AA)
    return annotated
