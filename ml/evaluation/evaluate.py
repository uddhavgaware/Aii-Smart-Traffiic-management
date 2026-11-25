"""
ml/evaluation/evaluate.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Evaluates trained YOLOv8 checkpoint on validation/test split and records real
Precision, Recall, mAP50, mAP50-95, Confusion Matrix, FPS, and inference latency.
Never fabricates accuracy numbers.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from ultralytics import YOLO


def evaluate_model(weights_path: Path, data_yaml: Path, out_dir: Path) -> dict:
    if not weights_path.exists():
        raise FileNotFoundError(
            f"Weights not found at {weights_path}. Model has NOT been trained yet."
        )
    if not data_yaml.exists():
        raise FileNotFoundError(f"Dataset YAML not found at {data_yaml}.")

    out_dir.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(weights_path))
    metrics = model.val(data=str(data_yaml), plots=True, save_json=True)

    # Measure inference latency & FPS on current hardware
    dummy = np.zeros((640, 640, 3), dtype=np.uint8)
    for _ in range(5):
        model(dummy, verbose=False)

    latencies = []
    for _ in range(30):
        t0 = time.perf_counter()
        model(dummy, verbose=False)
        latencies.append((time.perf_counter() - t0) * 1000.0)

    avg_ms = float(np.mean(latencies))
    report = {
        "weights": str(weights_path),
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
        "precision": float(metrics.box.mp),
        "recall": float(metrics.box.mr),
        "mAP50": float(metrics.box.map50),
        "mAP50_95": float(metrics.box.map),
        "avg_inference_ms": round(avg_ms, 2),
        "measured_fps": round(1000.0 / avg_ms, 2) if avg_ms > 0 else 0.0,
    }

    report_file = out_dir / "evaluation_report.json"
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[evaluate] Real evaluation saved to {report_file}")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=Path, default=Path("ml/models/checkpoints/best.pt"))
    parser.add_argument("--data", type=Path, default=Path("ml/datasets/traffic_dataset/data.yaml"))
    parser.add_argument("--out", type=Path, default=Path("ml/evaluation/results"))
    args = parser.parse_args()
    evaluate_model(args.weights, args.data, args.out)
