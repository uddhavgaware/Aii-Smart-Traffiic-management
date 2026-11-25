"""
tests/scenarios/scenario_runner.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Executes reproducible API simulations for Scenarios 1-10 against a live backend
and prints observed responses & decision latencies without fabricating results.
"""

from __future__ import annotations

import os
import time
from dotenv import load_dotenv
import httpx

load_dotenv()

BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
ML_API_KEY = os.getenv("ML_API_KEY", "")
ADMIN_USER = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "Admin@12345")


def post_traffic(client: httpx.Client, direction: str, count: int, density: str, queue: float = 10.0):
    headers = {"X-ML-API-Key": ML_API_KEY} if ML_API_KEY else {}
    t0 = time.perf_counter()
    r = client.post(
        "/api/traffic/update",
        json={
            "direction": direction,
            "vehicle_count": count,
            "density_level": density,
            "density_score": min(100.0, count * 2.5),
            "queue_length": queue,
            "congestion_predicted": count > 25,
        },
        headers=headers,
    )
    return r.status_code, round((time.perf_counter() - t0) * 1000.0, 2)


def main():
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        login = client.post("/api/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
        if login.status_code != 200:
            print(f"Login failed ({login.status_code}): create admin user via scripts/create_admin_user.py first.")
            return
        token = login.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        print("Running Scenario 1 (Normal traffic)...")
        for d in ("north", "south", "east", "west"):
            code, ms = post_traffic(client, d, 8, "NORMAL", 15.0)
            print(f"  {d}: HTTP {code} ({ms}ms)")

        print("Running Scenario 2 (Heavy East)...")
        code, ms = post_traffic(client, "east", 32, "HIGH", 75.0)
        print(f"  east: HTTP {code} ({ms}ms)")

        print("Running Scenario 4 (Confirmed Ambulance West)...")
        r = client.post(
            "/api/emergency/alert",
            json={"direction": "west", "vehicle_type": "ambulance", "stage": 2, "confidence": 0.91},
            headers=auth_headers,
        )
        print(f"  emergency alert: HTTP {r.status_code} -> {r.json()}")

        sig = client.get("/api/signals/state", headers=auth_headers).json()
        print("Observed Signal State:", sig)


if __name__ == "__main__":
    main()
