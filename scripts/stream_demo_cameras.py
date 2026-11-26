"""
Virtual 4-Camera Video Streamer
===============================
Streams the 4 directional video clips (low_traffic / medium_traffic / heavy_jam)
over WebSocket as if 4 phones were streaming simultaneously — ideal when you
don't have 4 physical mobile devices.

Usage examples:
    # Default mixed scenario against Render deployment (heavy North vs light East/West)
    python scripts/stream_demo_cameras.py

    # Choose traffic density per approach (low_traffic | medium_traffic | heavy_jam)
    python scripts/stream_demo_cameras.py --north heavy_jam --south low_traffic --east medium_traffic --west low_traffic

    # Stream to local backend instead of Render
    python scripts/stream_demo_cameras.py --ws ws://127.0.0.1:8000/ws
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import time
from pathlib import Path

import cv2
import websockets

ROOT = Path(__file__).resolve().parents[1]
CLIPS_DIR = ROOT / "ml" / "demo_clips" / "directions"
DEFAULT_WS = "wss://aii-smart-traffiic-management-backend.onrender.com/ws"


async def stream_direction(ws_url: str, direction: str, scenario: str, fps: float) -> None:
    clip_path = CLIPS_DIR / direction / f"{scenario}.mp4"
    if not clip_path.exists():
        print(f"[{direction}] Missing clip: {clip_path}")
        return

    cap = cv2.VideoCapture(str(clip_path))
    if not cap.isOpened():
        print(f"[{direction}] Failed to open: {clip_path}")
        return

    device_id = f"virtual-cam-{direction}"
    interval = 1.0 / max(1.0, fps)

    while True:
        try:
            async with websockets.connect(f"{ws_url}?client_type=mobile", ping_interval=20, ping_timeout=20) as ws:
                print(f"[{direction.upper()}] Connected ({scenario}.mp4 @ {fps} FPS)")
                while True:
                    t0 = time.perf_counter()
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ok, frame = cap.read()
                    if not ok or frame is None:
                        await asyncio.sleep(0.2)
                        continue

                    h, w = frame.shape[:2]
                    ok_enc, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                    if ok_enc:
                        data_url = "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")
                        await ws.send(json.dumps({
                            "type": "camera_frame",
                            "payload": {
                                "direction": direction,
                                "device_id": device_id,
                                "junction_code": "JCT-001",
                                "image": data_url,
                                "resolution": f"{w}x{h}",
                                "timestamp": int(time.time() * 1000),
                            },
                        }))

                    # Drain non-blocking ACK/ping responses so WS buffer never stalls
                    while True:
                        try:
                            await asyncio.wait_for(ws.recv(), timeout=0.001)
                        except asyncio.TimeoutError:
                            break

                    elapsed = time.perf_counter() - t0
                    await asyncio.sleep(max(0.01, interval - elapsed))
        except asyncio.CancelledError:
            break
        except Exception as exc:
            print(f"[{direction.upper()}] Reconnecting in 3s ({exc})")
            await asyncio.sleep(3.0)

    cap.release()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Stream 4 virtual traffic cameras over WebSocket")
    parser.add_argument("--ws", default=DEFAULT_WS, help="Backend WebSocket URL")
    parser.add_argument("--fps", type=float, default=6.0, help="Frames per second per virtual camera (default: 6)")
    parser.add_argument("--north", default="heavy_jam", choices=["low_traffic", "medium_traffic", "heavy_jam"])
    parser.add_argument("--south", default="medium_traffic", choices=["low_traffic", "medium_traffic", "heavy_jam"])
    parser.add_argument("--east", default="low_traffic", choices=["low_traffic", "medium_traffic", "heavy_jam"])
    parser.add_argument("--west", default="medium_traffic", choices=["low_traffic", "medium_traffic", "heavy_jam"])
    args = parser.parse_args()

    print(f"Streaming 4 virtual cameras -> {args.ws} ({args.fps} FPS each)")
    print("Press Ctrl+C to stop.")
    await asyncio.gather(
        stream_direction(args.ws, "north", args.north, args.fps),
        stream_direction(args.ws, "south", args.south, args.fps),
        stream_direction(args.ws, "east", args.east, args.fps),
        stream_direction(args.ws, "west", args.west, args.fps),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped virtual camera streams.")
