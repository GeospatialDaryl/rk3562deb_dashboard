from __future__ import annotations

import json
import threading
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

from rk3562deb_dashboard.server import DashboardServer

SNAPSHOT_KEYS = (
    "timestamp",
    "host",
    "cpu",
    "memory",
    "swap",
    "processes",
    "disks",
    "block_io",
    "network",
    "thermal",
    "power",
    "npu",
    "rockchip",
)


@pytest.fixture()
def base_url(tmp_path: Path) -> Iterator[str]:
    server = DashboardServer(("127.0.0.1", 0), root=tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_healthz(base_url: str) -> None:
    with urllib.request.urlopen(f"{base_url}/healthz") as response:
        assert response.status == 200
        assert json.loads(response.read()) == {"ok": True}


def test_snapshot_has_all_sections(base_url: str) -> None:
    with urllib.request.urlopen(f"{base_url}/api/snapshot") as response:
        assert response.status == 200
        assert response.headers["Content-Type"].startswith("application/json")
        snapshot = json.loads(response.read())
    for key in SNAPSHOT_KEYS:
        assert key in snapshot


def test_root_serves_index(base_url: str) -> None:
    with urllib.request.urlopen(f"{base_url}/") as response:
        assert response.status == 200
        assert b"RK3562 Debian Dashboard" in response.read()


def test_history_endpoint_returns_compact_points(base_url: str) -> None:
    with urllib.request.urlopen(f"{base_url}/api/history") as response:
        assert response.status == 200
        history = json.loads(response.read())
    assert history["interval_seconds"] == 2.0
    assert len(history["points"]) >= 1
    point = history["points"][0]
    for key in ("t", "cpu", "mem", "temp", "sd_write", "emmc_write"):
        assert key in point


def test_history_point_reduces_snapshot() -> None:
    from rk3562deb_dashboard.server import history_point

    snapshot = {
        "timestamp": 1000.0,
        "cpu": {"total": {"usage_percent": 42.0}},
        "memory": {"usage_percent": 55.0},
        "thermal": [
            {"temperature_c": 41.0},
            {"temperature_c": 45.5},
            {"temperature_c": None},
        ],
        "block_io": [
            {"kind": "SD", "write_bytes_per_sec": 0},
            {"kind": "MMC", "write_bytes_per_sec": 8192},
        ],
    }

    point = history_point(snapshot)

    assert point == {
        "t": 1000.0,
        "cpu": 42.0,
        "mem": 55.0,
        "temp": 45.5,
        "sd_write": 0,
        "emmc_write": 8192,
    }
