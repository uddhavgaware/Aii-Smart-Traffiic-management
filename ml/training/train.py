"""
ml/training/train.py
~~~~~~~~~~~~~~~~~~~~
Fine-tunes YOLOv8 on the custom 7-class traffic dataset.
Copies best checkpoint to ml/models/checkpoints/best.pt upon completion.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import yaml


def train(config_path: Path, resume: bool = False) -> None:
    from ultralytics import YOLO

    with open(config_path, "r") as fh:
        cfg = yaml.safe_load(fh)["training"]

    data_yaml = Path(cfg["data_yaml"])
    if not data_yaml.exists():
        raise FileNotFoundError(
            f"Dataset config '{data_yaml}' not found. Run ml/training/prepare_dataset.py first."
        )

    model = YOLO(cfg["model"])
    results = model.train(
        data=str(data_yaml),
        epochs=int(cfg.get("epochs", 100)),
        imgsz=int(cfg.get("imgsz", 640)),
        batch=int(cfg.get("batch", 16)),
        device=cfg.get("device", 0),
        workers=int(cfg.get("workers", 4)),
        project=cfg.get("project", "models/training_runs"),
        name=cfg.get("name", "traffic_v1"),
        hsv_h=float(cfg.get("hsv_h", 0.015)),
        hsv_s=float(cfg.get("hsv_s", 0.7)),
        hsv_v=float(cfg.get("hsv_v", 0.4)),
        degrees=float(cfg.get("degrees", 5.0)),
        translate=float(cfg.get("translate", 0.1)),
        scale=float(cfg.get("scale", 0.5)),
        fliplr=float(cfg.get("fliplr", 0.5)),
        mosaic=float(cfg.get("mosaic", 1.0)),
        mixup=float(cfg.get("mixup", 0.0)),
        patience=int(cfg.get("patience", 20)),
        optimizer=cfg.get("optimizer", "AdamW"),
        lr0=float(cfg.get("lr0", 0.01)),
        lrf=float(cfg.get("lrf", 0.01)),
        resume=resume,
    )

    best_src = Path(results.save_dir) / "weights" / "best.pt"
    ckpt_dest = Path("ml/models/checkpoints/best.pt")
    ckpt_dest.parent.mkdir(parents=True, exist_ok=True)
    if best_src.exists():
        shutil.copy2(best_src, ckpt_dest)
        print(f"[train] Copied trained best weights -> {ckpt_dest}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("ml/config/training_config.yaml"))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    train(args.config, resume=args.resume)
