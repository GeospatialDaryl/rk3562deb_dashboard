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
    "network",
    "thermal",
    "power",
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
