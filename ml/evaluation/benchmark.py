"""
ml/evaluation/benchmark.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
Measures actual RTX 3050 GPU VRAM, CPU usage, per-frame latency, and
simulated 4-camera simultaneous inference throughput.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import psutil
import torch

from ml.inference.model import TrafficDetectionModel


def run_benchmark(config_path: str = "ml/config/model_config.yaml", frames: int = 80) -> dict:
    model = TrafficDetectionModel(config_path)
    test_frames = [
        np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
        for _ in range(4)
    ]

    latencies_ms = []
    cpu_samples = []
    t_start = time.perf_counter()

    for i in range(frames):
        frame = test_frames[i % 4]
        res = model.detect(frame)
        latencies_ms.append(res.inference_ms)
        if i % 10 == 0:
            cpu_samples.append(psutil.cpu_percent(interval=None))

    total_s = time.perf_counter() - t_start
    vram_allocated_mb = (
        round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2)
        if torch.cuda.is_available()
        else 0.0
    )

    report = {
        "device": str(model.device),
        "fp16": model.fp16,
        "model_trained": model.model_trained,
        "frames_processed": frames,
        "total_seconds": round(total_s, 3),
        "aggregate_fps": round(frames / total_s, 2),
        "per_camera_fps_4cam": round((frames / total_s) / 4.0, 2),
        "mean_inference_ms": round(float(np.mean(latencies_ms)), 2),
        "p95_inference_ms": round(float(np.percentile(latencies_ms, 95)), 2),
        "peak_vram_mb": vram_allocated_mb,
        "mean_cpu_percent": round(float(np.mean(cpu_samples)) if cpu_samples else 0.0, 1),
    }

    out = Path("ml/evaluation/results/benchmark_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    run_benchmark()
