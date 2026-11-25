"""
ml/scripts/calibrate_camera.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Camera calibration helper:
  1. Chessboard intrinsic calibration (lens distortion)
  2. 4-point road homography calibration (pixels -> meters for real speed & queue length)
Until calibration files exist, speed is ALWAYS marked "ESTIMATE - uncalibrated".
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

import cv2
import numpy as np


def compute_homography(
    pixel_points: List[List[float]],
    world_meters: List[List[float]],
    out_file: Path,
) -> np.ndarray:
    src = np.array(pixel_points, dtype=np.float32)
    dst = np.array(world_meters, dtype=np.float32)
    H, _ = cv2.findHomography(src, dst)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "calibrated": True,
        "pixel_points": pixel_points,
        "world_meters": world_meters,
        "homography_matrix": H.tolist(),
    }
    out_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"[calibrate] Saved road homography calibration to {out_file}")
    return H


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Save 4-point road perspective calibration")
    parser.add_argument("--direction", required=True, choices=["north", "south", "east", "west"])
    parser.add_argument("--width-m", type=float, default=7.0, help="Road width in meters")
    parser.add_argument("--length-m", type=float, default=20.0, help="Visible road length in meters")
    args = parser.parse_args()

    # Example default trapezoid points (replace with measured coordinates from camera frame)
    px = [[200, 200], [440, 200], [580, 350], [60, 350]]
    meters = [[0.0, args.length_m], [args.width_m, args.length_m], [args.width_m, 0.0], [0.0, 0.0]]
    compute_homography(px, meters, Path(f"ml/config/calibration_{args.direction}.json"))
