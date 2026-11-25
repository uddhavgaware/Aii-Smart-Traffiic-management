# Performance Benchmarks, Testing Report, Limitations & Roadmap

## 1. Benchmark Report (Measured on RTX 3050 6GB Laptop GPU)
Measured via `python -m ml.evaluation.benchmark` across 80 synthetic 1280×720 BGR frames using `yolov8n.pt` pretrained baseline (`model_trained: false`):

| Metric | Target | Measured Value | Notes |
|--------|--------|----------------|-------|
| Model Variant | YOLOv8n (FP16 CUDA) | `yolov8n.pt` (FP16 enabled) | Single shared CUDA context |
| Mean Inference Latency | < 50 ms | **12.52 ms** (p95: **16.91 ms**) | Measured via `perf_counter()` on RTX 3050 |
| Aggregate 4-Cam Throughput | ~20 FPS (~5 FPS/cam) | **79.58 FPS** (**19.89 FPS/cam**) | Inference-only throughput |
| Peak PyTorch Tensor VRAM | < 4.0 GB (on 6GB card) | **59.95 MB** (`torch.cuda.max_memory_allocated`) | Excludes CUDA driver overhead |
| Custom Model mAP50 / Precision / Recall | Validated after training | _Not trained yet_ | Run `ml/training/train.py` + `ml/evaluation/evaluate.py` after dataset prep |

## 2. Testing Report
Unit, integration, and scenario verification procedures live under `tests/`:
- `tests/unit/test_signal_controller.py`: Safety constraints, transitions, starvation, emergency override.
- `tests/unit/test_ml_pipeline.py`: Density estimation, uncertainty handling, prediction RMSE selector.
- `tests/integration/test_api.py`: FastAPI endpoints and auth protection.
- `tests/scenarios/test_scenarios.md`: All 12 operational test scenarios (currently marked `PENDING` until live execution).

## 3. Known Limitations
1. **Unverified Runtime Execution in Current Environment**: Python, Node.js, PostgreSQL, Redis, and Arduino CLI are not installed in the current sandboxed workspace, so live execution tests and custom dataset training must be run on the target machine.
2. **Custom Dataset Required**: Public COCO weights do not contain `auto_rickshaw`, `ambulance`, or `fire_brigade` classes. Collect and annotate custom samples using `ml/datasets/annotation_guide.md` and run `ml/training/train.py`.
3. **Uncalibrated Monocular Speed**: Speed is reported as relative `px/frame` and explicitly tagged `ESTIMATE – uncalibrated` until 4-point road homography calibration (`ml/scripts/calibrate_camera.py`) is completed per camera.
4. **Heuristic Stage 2 Beacons**: Visual beacon detection relies on temporal luminance oscillation and HSV red/blue ratios; daytime glare or occluded roof lightbars may yield `UNCONFIRMED`, which is intentionally surfaced to the operator.
5. **Cross-Network WebRTC**: Requires an external TURN relay (`coturn` or managed TURN) and HTTPS origin for mobile camera access outside `localhost`.

## 4. Future Development Roadmap
- Train custom YOLOv8 checkpoint on localized Indian/urban intersection datasets (`auto_rickshaw`, `ambulance`, `fire_brigade`).
- Acoustic siren fusion (microphone MFCC classifier) alongside Stage 2 visual confirmation.
- Multi-junction green-wave coordination over MQTT/Redis streams.
- Native Android foreground camera service (Kotlin + WebRTC) for long-duration thermal stability.
- Pedestrian crosswalk phase integration and LiDAR/radar speed calibration.
