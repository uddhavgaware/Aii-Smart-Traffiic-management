"""
System-wide performance benchmark script (backend response latency + ML inference).
Run on target laptop (RTX 3050 + i5) and record actual measured numbers.
"""

from __future__ import annotations

import time
import httpx


def benchmark_backend(base_url: str = "http://localhost:8000", iterations: int = 30) -> dict:
    latencies = []
    with httpx.Client(base_url=base_url, timeout=5.0) as client:
        for _ in range(iterations):
            t0 = time.perf_counter()
            r = client.get("/health")
            r.raise_for_status()
            latencies.append((time.perf_counter() - t0) * 1000.0)
    avg_ms = sum(latencies) / len(latencies)
    return {"requests": iterations, "avg_response_ms": round(avg_ms, 2), "max_ms": round(max(latencies), 2)}


if __name__ == "__main__":
    print(benchmark_backend())
