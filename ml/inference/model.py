"""
ml/inference/model.py
~~~~~~~~~~~~~~~~~~~~~
Wraps a YOLOv8 model for traffic detection.

Responsibilities:
  - Load custom weights when available; fall back to YOLOv8n pretrained.
  - Support FP16 (half-precision) inference on CUDA with automatic fallback.
  - Warm-up the model to prime CUDA JIT caches.
  - Return structured DetectionResult objects.
  - Never claim the model is trained if no custom weights exist.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data-classes
# ---------------------------------------------------------------------------

@dataclass
class Detection:
    """Single detection from one inference pass."""
    bbox_xyxy: np.ndarray          # [x1, y1, x2, y2] absolute pixels
    confidence: float
    class_id: int
    class_name: str
    is_emergency: bool = False


@dataclass
class DetectionResult:
    """All detections for a single frame."""
    detections: list[Detection] = field(default_factory=list)
    frame_shape: tuple[int, int, int] = (0, 0, 3)   # H, W, C
    inference_ms: float = 0.0
    model_trained: bool = True      # False → weights missing / NOT_TRAINED
    device: str = "cpu"
    fp16: bool = False
    timestamp: float = field(default_factory=time.time)

    @property
    def num_detections(self) -> int:
        return len(self.detections)

    @property
    def emergency_detections(self) -> list[Detection]:
        return [d for d in self.detections if d.is_emergency]


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class TrafficDetectionModel:
    """
    YOLOv8-based traffic detection model.

    Loading priority
    ----------------
    1. ``config.model.weights``    — custom fine-tuned checkpoint
    2. ``config.model.pretrained_fallback`` — standard Ultralytics pretrained
    3. Hard-coded ``yolov8n.pt``   — absolute last resort

    When no custom weights are found the model still runs (pretrained YOLOv8
    classes) but ``DetectionResult.model_trained`` is set to ``False`` so the
    API layer can surface a NOT_TRAINED flag to callers.
    """

    EMERGENCY_CLASS_IDS: frozenset[int] = frozenset({5, 6})

    def __init__(self, config_path: str) -> None:
        self._config = self._load_config(config_path)
        self._model_cfg = self._config["model"]
        self._inf_cfg = self._config["inference"]

        self.device = self._resolve_device(self._inf_cfg.get("device", "cuda"))
        self.fp16: bool = self._inf_cfg.get("fp16", False) and self.device.type == "cuda"
        self.conf_threshold: float = self._model_cfg.get("confidence_threshold", 0.45)
        self.iou_threshold: float = self._model_cfg.get("iou_threshold", 0.45)
        self.max_det: int = self._model_cfg.get("max_detections", 100)
        self.input_size: int = self._model_cfg.get("input_size", 640)

        self._class_map: dict[int, str] = {
            int(k): v for k, v in self._model_cfg.get("classes", {}).items()
        }

        self.model_trained: bool = False
        self._model = self._load_model()
        self._warmup(self._inf_cfg.get("warmup_iterations", 3))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_config(config_path: str) -> dict:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config not found: {config_path}")
        with open(path, "r") as fh:
            return yaml.safe_load(fh)

    @staticmethod
    def _resolve_device(device_str: str) -> torch.device:
        if device_str == "cuda":
            if torch.cuda.is_available():
                logger.info("CUDA available → using GPU: %s",
                            torch.cuda.get_device_name(0))
                return torch.device("cuda")
            else:
                logger.warning(
                    "CUDA requested but not available — falling back to CPU. "
                    "Inference will be significantly slower."
                )
                return torch.device("cpu")
        return torch.device("cpu")

    def _load_model(self):
        """Load YOLOv8; sets self.model_trained accordingly."""
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "ultralytics package not installed. Run: pip install ultralytics"
            ) from exc

        # --- Try custom weights first ---
        custom_weights = Path(self._model_cfg.get("weights", ""))
        if custom_weights.exists():
            logger.info("Loading custom weights: %s", custom_weights)
            model = YOLO(str(custom_weights))
            self.model_trained = True
        else:
            if str(custom_weights) not in ("", "."):
                logger.warning(
                    "Custom weights not found at '%s'. "
                    "Falling back to pretrained — model is NOT custom-trained. "
                    "API will expose NOT_TRAINED flag.",
                    custom_weights,
                )
            fallback = self._model_cfg.get("pretrained_fallback", "yolov8n.pt")
            logger.info("Loading pretrained fallback: %s", fallback)
            model = YOLO(fallback)
            self.model_trained = False

        # --- Move to device; defer FP16 conversion to Ultralytics AutoBackend after Conv+BN fuse ---
        model.to(self.device)
        if self.fp16 and self.device.type != "cuda":
            logger.warning("FP16 ignored on CPU.")
            self.fp16 = False

        return model

    def _warmup(self, iterations: int) -> None:
        """Run dummy inference to prime CUDA JIT caches and validate FP16."""
        if iterations <= 0:
            return
        dummy = np.zeros((self.input_size, self.input_size, 3), dtype=np.uint8)
        logger.info("Warming up model (%d iterations, fp16=%s)…", iterations, self.fp16)
        for i in range(iterations):
            try:
                self._model(
                    dummy,
                    conf=self.conf_threshold,
                    iou=self.iou_threshold,
                    max_det=self.max_det,
                    imgsz=self.input_size,
                    half=self.fp16,
                    device=0 if self.device.type == "cuda" else "cpu",
                    verbose=False,
                )
            except Exception as exc:  # noqa: BLE001
                if self.fp16:
                    logger.warning("FP16 warm-up failed (%s) — falling back to FP32.", exc)
                    self.fp16 = False
                    self._model(
                        dummy,
                        conf=self.conf_threshold,
                        iou=self.iou_threshold,
                        max_det=self.max_det,
                        imgsz=self.input_size,
                        half=False,
                        device=0 if self.device.type == "cuda" else "cpu",
                        verbose=False,
                    )
                else:
                    raise
        logger.info("Warm-up complete.")

    def _map_class(self, class_id: int) -> str:
        """Return human-readable class name; use custom map only when custom-trained weights are loaded."""
        if self.model_trained and self._class_map and class_id in self._class_map:
            return self._class_map[class_id]
        try:
            return self._model.names[class_id]
        except (KeyError, AttributeError):
            return f"class_{class_id}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray) -> DetectionResult:
        """
        Run YOLOv8 inference on a single BGR frame (OpenCV format).

        Parameters
        ----------
        frame : np.ndarray
            H×W×3 uint8 BGR frame.

        Returns
        -------
        DetectionResult
        """
        if frame is None or frame.size == 0:
            logger.warning("detect() received empty/None frame.")
            return DetectionResult(model_trained=self.model_trained, device=str(self.device))

        t0 = time.perf_counter()

        results = self._model(
            frame,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            max_det=self.max_det,
            imgsz=self.input_size,
            half=self.fp16,
            device=0 if self.device.type == "cuda" else "cpu",
            verbose=False,
        )

        inference_ms = (time.perf_counter() - t0) * 1000.0
        detections: list[Detection] = []

        if results and results[0].boxes is not None:
            boxes = results[0].boxes
            for i in range(len(boxes)):
                xyxy = boxes.xyxy[i].cpu().numpy().astype(np.float32)
                conf = float(boxes.conf[i].cpu().numpy())
                cls  = int(boxes.cls[i].cpu().numpy())
                name = self._map_class(cls)
                # Only treat classes 5/6 as emergency when custom-trained weights are active
                # (in COCO pretrained weights, class 5 is 'bus' and 6 is 'train').
                is_em = self.model_trained and (cls in self.EMERGENCY_CLASS_IDS)
                detections.append(
                    Detection(
                        bbox_xyxy=xyxy,
                        confidence=conf,
                        class_id=cls,
                        class_name=name,
                        is_emergency=is_em,
                    )
                )

        return DetectionResult(
            detections=detections,
            frame_shape=frame.shape,
            inference_ms=inference_ms,
            model_trained=self.model_trained,
            device=str(self.device),
            fp16=self.fp16,
        )

    def get_model_info(self) -> dict:
        """Return metadata about the loaded model."""
        gpu_name: Optional[str] = None
        if self.device.type == "cuda":
            try:
                gpu_name = torch.cuda.get_device_name(0)
            except Exception:  # noqa: BLE001
                gpu_name = "unknown"
        return {
            "architecture": self._model_cfg.get("architecture", "yolov8n"),
            "model_trained": self.model_trained,
            "not_trained_flag": not self.model_trained,
            "num_classes": self._model_cfg.get("num_classes", 7),
            "classes": self._class_map,
            "device": str(self.device),
            "gpu_name": gpu_name,
            "fp16": self.fp16,
            "input_size": self.input_size,
            "conf_threshold": self.conf_threshold,
            "iou_threshold": self.iou_threshold,
        }
