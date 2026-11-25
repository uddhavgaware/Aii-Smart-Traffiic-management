"""Test ML inference on an image or video file and print structured detections."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from ml.inference.model import TrafficDetectionModel


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True, help="Path to test image or video")
    parser.add_argument("--config", type=str, default="ml/config/model_config.yaml")
    args = parser.parse_args()

    model = TrafficDetectionModel(args.config)
    if args.source.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}:
        frame = cv2.imread(str(args.source))
        res = model.detect(frame)
        print(f"Detections: {res.num_detections} | Inference: {res.inference_ms:.2f}ms | Trained: {res.model_trained}")
        for d in res.detections:
            print(f"  - {d.class_name}: conf={d.confidence:.2f}, box={d.bbox_xyxy.tolist()}")
    else:
        cap = cv2.VideoCapture(str(args.source))
        frames = 0
        while cap.isOpened() and frames < 50:
            ok, frame = cap.read()
            if not ok:
                break
            res = model.detect(frame)
            frames += 1
            print(f"Frame {frames}: {res.num_detections} vehicles ({res.inference_ms:.1f}ms)")
        cap.release()


if __name__ == "__main__":
    main()
