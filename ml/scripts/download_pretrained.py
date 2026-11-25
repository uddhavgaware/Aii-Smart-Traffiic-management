"""Download YOLOv8n pretrained baseline weights into ml/models/."""

from __future__ import annotations

from ultralytics import YOLO


def main() -> None:
    model = YOLO("yolov8n.pt")
    print(f"Downloaded/verified pretrained weights: {model.ckpt_path}")


if __name__ == "__main__":
    main()
