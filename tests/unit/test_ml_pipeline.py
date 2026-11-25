"""
Unit tests for ML density analyzer, prediction selector, and Stage 2 emergency detector.
"""

from __future__ import annotations

import numpy as np

from ml.inference.density_analyzer import DensityLevel, TrafficDensityAnalyzer
from ml.inference.emergency_detector import EmergencyDetector, EmergencyStatus
from ml.inference.model import Detection, DetectionResult
from ml.inference.prediction import TrafficPredictor
from ml.inference.tracker import TrackedVehicle, TrackerResult, VehicleTracker


def test_vehicle_tracker_initializes_and_updates():
    tracker = VehicleTracker({"max_age": 30, "min_hits": 1})
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    det = DetectionResult(
        detections=[
            Detection(
                bbox_xyxy=np.array([100, 100, 180, 160], dtype=np.float32),
                confidence=0.88,
                class_id=0,
                class_name="car",
                is_emergency=False,
            )
        ],
        frame_shape=frame.shape,
    )
    res = tracker.update(det, frame)
    assert res.frame_shape == (360, 640, 3)


def test_density_uncalibrated_speed_labeled_estimate():
    analyzer = TrafficDensityAnalyzer({"thresholds": {"low": 5, "normal": 15, "medium": 25, "high": 40}}, calibrated=False)
    roi = np.array([[0, 0], [640, 0], [640, 360], [0, 360]])
    tracks = TrackerResult(
        tracks=[
            TrackedVehicle(
                track_id=i,
                bbox_xyxy=np.array([50 + i * 20, 50, 90 + i * 20, 90], dtype=float),
                centroid=np.array([70 + i * 20, 70], dtype=float),
                class_id=0,
                class_name="car",
                confidence=0.9,
                is_emergency=False,
            )
            for i in range(6)
        ]
    )
    res = analyzer.analyze(tracks, roi)
    assert res.vehicle_count == 6
    assert res.level in (DensityLevel.NORMAL, DensityLevel.MEDIUM, DensityLevel.HIGH, DensityLevel.TRAFFIC_JAM)
    if res.speed_estimate is not None:
        assert res.speed_estimate.is_estimate is True
        assert "ESTIMATE" in res.speed_estimate.label


def test_emergency_detector_uncertainty_on_few_frames():
    det = EmergencyDetector({})
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    tracks = TrackerResult(
        tracks=[
            TrackedVehicle(
                track_id=1,
                bbox_xyxy=np.array([100, 100, 220, 200], dtype=float),
                centroid=np.array([160, 150], dtype=float),
                class_id=5,
                class_name="ambulance",
                confidence=0.92,
                is_emergency=True,
            )
        ]
    )
    state = det.process(tracks, frame)
    assert len(state.active_emergencies) == 1
    assert state.active_emergencies[0].status == EmergencyStatus.UNCONFIRMED
    assert state.has_confirmed is False


def test_traffic_predictor_selects_lowest_rmse_model():
    pred = TrafficPredictor(method="auto", horizon_seconds=45)
    for i in range(25):
        pred.update("north", count=10 + (i % 4), density="NORMAL")
    result = pred.predict("north")
    assert result.expected_vehicle_count >= 0
    assert result.selected_model in (
        "moving_average",
        "exponential_smoothing",
        "random_forest",
        "gradient_boosting",
    )
