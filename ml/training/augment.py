"""
ml/training/augment.py
~~~~~~~~~~~~~~~~~~~~~~
Traffic-oriented OpenCV augmentations (rain/low-light/blur/flip) preserving YOLO boxes.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np


def adjust_brightness_contrast(img: np.ndarray, alpha: float, beta: float) -> np.ndarray:
    return cv2.convertScaleAbs(img, alpha=alpha, beta=beta)


def horizontal_flip(img: np.ndarray, labels: List[Tuple[int, float, float, float, float]]):
    flipped = cv2.flip(img, 1)
    out = [(cls, 1.0 - xc, yc, w, h) for (cls, xc, yc, w, h) in labels]
    return flipped, out


def add_motion_blur(img: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    kernel = np.zeros((kernel_size, kernel_size), dtype=np.float32)
    kernel[kernel_size // 2, :] = np.ones(kernel_size, dtype=np.float32) / kernel_size
    return cv2.filter2D(img, -1, kernel)


def augment_directory(images_dir: Path, labels_dir: Path, copies_per_image: int = 1) -> int:
    created = 0
    for img_path in list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.png")):
        lbl_path = labels_dir / f"{img_path.stem}.txt"
        if not lbl_path.exists():
            continue
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        labels = []
        for line in lbl_path.read_text(encoding="utf-8").splitlines():
            parts = line.strip().split()
            if len(parts) == 5:
                labels.append((int(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])))

        for i in range(copies_per_image):
            aug_img = img.copy()
            aug_lbl = list(labels)
            if random.random() < 0.5:
                aug_img, aug_lbl = horizontal_flip(aug_img, aug_lbl)
            aug_img = adjust_brightness_contrast(aug_img, random.uniform(0.75, 1.25), random.uniform(-25, 25))
            if random.random() < 0.3:
                aug_img = add_motion_blur(aug_img, 5)

            out_img = images_dir / f"{img_path.stem}_aug{i}{img_path.suffix}"
            out_lbl = labels_dir / f"{img_path.stem}_aug{i}.txt"
            cv2.imwrite(str(out_img), aug_img)
            out_lbl.write_text(
                "\n".join(f"{c} {x:.6f} {y:.6f} {w:.6f} {h:.6f}" for c, x, y, w, h in aug_lbl),
                encoding="utf-8",
            )
            created += 1
    return created
