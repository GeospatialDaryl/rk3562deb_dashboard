from __future__ import annotations

import json
import threading
import urllib.error
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


def test_root_serves_launcher(base_url: str) -> None:
    with urllib.request.urlopen(f"{base_url}/") as response:
        assert response.status == 200
        assert b"RK3562 Launcher" in response.read()


def test_dashboard_route_serves_index(base_url: str) -> None:
    with urllib.request.urlopen(f"{base_url}/dashboard") as response:
        assert response.status == 200
        assert b"RK3562 Debian Dashboard" in response.read()


def test_launcher_status_shape(base_url: str) -> None:
    from rk3562deb_dashboard.server import CV_DEMOS

    with urllib.request.urlopen(f"{base_url}/api/launcher-status") as response:
        assert response.status == 200
        status = json.loads(response.read())
    for key in ("active_app", "battery", "power_profile", "cv_demo", "cv_demos"):
        assert key in status
    assert status["cv_demos"] == list(CV_DEMOS)
    assert set(status["battery"]) == {"status", "capacity_percent"}


def _post(url: str, body: bytes | None = None) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(url, data=body or b"", method="POST")
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_set_cv_demo_writes_state_file(
    base_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    status, payload = _post(
        f"{base_url}/api/control/set-cv-demo", json.dumps({"demo": "resnet"}).encode()
    )
    assert status == 200
    assert payload == {"ok": True, "demo": "resnet"}
    assert (tmp_path / "cv-demo-current").read_text() == "resnet\n"


def test_set_cv_demo_rejects_unknown_demo(
    base_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    status, payload = _post(
        f"{base_url}/api/control/set-cv-demo", json.dumps({"demo": "rm -rf"}).encode()
    )
    assert status == 400
    assert payload["ok"] is False
    assert not (tmp_path / "cv-demo-current").exists()


def test_set_cv_demo_rejects_invalid_json(base_url: str) -> None:
    status, payload = _post(f"{base_url}/api/control/set-cv-demo", b"not json")
    assert status == 400
    assert payload["ok"] is False


def test_unknown_control_action_is_404(base_url: str) -> None:
    status, payload = _post(f"{base_url}/api/control/definitely-not-real")
    assert status == 404
    assert payload["ok"] is False


def _fake_nmcli_factory(
    calls: list[list[str]],
    connect_rc: int = 0,
    connect_stderr: str = "",
    profile_appears_after_connect: bool = False,
) -> object:
    """Stateful stand-in for server._nmcli, dispatching on argv."""
    import subprocess

    state = {"connect_attempted": False}

    def fake(args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        joined = " ".join(args)
        if "device wifi list" in joined:
            stdout = "yes:Home:92:WPA2\nno:Guest:60:WPA2\nno:Cafe:40:WPA2\n"
        elif "connection show" in joined:
            stdout = "Home:802-11-wireless\nlo:loopback\n"
            if profile_appears_after_connect and state["connect_attempted"]:
                stdout += "Cafe:802-11-wireless\n"
        elif "radio" in joined:
            stdout = "enabled\n"
        elif "device show" in joined:
            stdout = (
                "GENERAL.CONNECTION:Home\nGENERAL.STATE:100 (connected)\n"
                "IP4.ADDRESS[1]:192.168.1.23/24\n"
            )
        elif "wifi connect" in joined or "connection up" in joined:
            state["connect_attempted"] = True
            return subprocess.CompletedProcess(args, connect_rc, "", connect_stderr)
        else:
            stdout = ""
        return subprocess.CompletedProcess(args, 0, stdout, "")

    return fake


def test_wifi_status_shape(base_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from rk3562deb_dashboard import server

    calls: list[list[str]] = []
    monkeypatch.setattr(server, "_nmcli", _fake_nmcli_factory(calls))
    with urllib.request.urlopen(f"{base_url}/api/wifi/status") as response:
        status = json.loads(response.read())
    assert status == {
        "radio": "enabled",
        "device_state": "100 (connected)",
        "ssid": "Home",
        "signal": 92,
        "ip4": "192.168.1.23/24",
    }


def test_wifi_scan_merges_and_flags_known(
    base_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from rk3562deb_dashboard import server

    calls: list[list[str]] = []
    monkeypatch.setattr(server, "_nmcli", _fake_nmcli_factory(calls))
    with urllib.request.urlopen(f"{base_url}/api/wifi/scan") as response:
        payload = json.loads(response.read())
    assert payload["ok"] is True
    by_ssid = {n["ssid"]: n for n in payload["networks"]}
    assert by_ssid["Home"]["known"] is True and by_ssid["Home"]["in_use"] is True
    assert by_ssid["Guest"]["known"] is False
    assert any("--rescan" in call and "no" in call for call in calls)


def test_wifi_connect_validation(base_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from rk3562deb_dashboard import server

    monkeypatch.setattr(server, "_nmcli", _fake_nmcli_factory([]))
    status, payload = _post(f"{base_url}/api/wifi/connect", json.dumps({}).encode())
    assert status == 400 and "ssid" in str(payload["error"])
    status, payload = _post(
        f"{base_url}/api/wifi/connect", json.dumps({"ssid": "Cafe", "psk": "shrt"}).encode()
    )
    assert status == 400
    assert payload["error"] == "Password must be 8-63 characters"


def test_wifi_writes_forbidden_for_remote_clients(
    base_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from rk3562deb_dashboard import wifi as wifi_module

    monkeypatch.setattr(wifi_module, "is_local", lambda addr: False)
    status, payload = _post(
        f"{base_url}/api/wifi/connect", json.dumps({"ssid": "Cafe"}).encode()
    )
    assert status == 403 and payload["ok"] is False


def test_wifi_connect_wrong_password_cleans_up_profile(
    base_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from rk3562deb_dashboard import server

    calls: list[list[str]] = []
    monkeypatch.setattr(
        server,
        "_nmcli",
        _fake_nmcli_factory(
            calls,
            connect_rc=4,
            connect_stderr="Error: Secrets were required, but not provided.",
            profile_appears_after_connect=True,
        ),
    )
    status, payload = _post(
        f"{base_url}/api/wifi/connect",
        json.dumps({"ssid": "Cafe", "psk": "wrongpass"}).encode(),
    )
    assert status == 502
    assert payload["error"] == "wrong-password"
    assert ["connection", "delete", "id", "Cafe"] in calls


def test_wifi_forget(base_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from rk3562deb_dashboard import server

    calls: list[list[str]] = []
    monkeypatch.setattr(server, "_nmcli", _fake_nmcli_factory(calls))
    status, payload = _post(
        f"{base_url}/api/wifi/forget", json.dumps({"name": "Guest"}).encode()
    )
    assert status == 200 and payload["ok"] is True
    assert ["connection", "delete", "id", "Guest"] in calls


def test_launcher_status_includes_wifi(
    base_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from rk3562deb_dashboard import server

    monkeypatch.setattr(server, "_nmcli", _fake_nmcli_factory([]))
    with urllib.request.urlopen(f"{base_url}/api/launcher-status") as response:
        status = json.loads(response.read())
    assert status["wifi"] == {"ssid": "Home", "signal": 92}


def test_wifi_route_serves_page(base_url: str) -> None:
    with urllib.request.urlopen(f"{base_url}/wifi") as response:
        assert response.status == 200
        assert b"<title>WiFi</title>" in response.read()


def test_history_endpoint_returns_compact_points(base_url: str) -> None:
    with urllib.request.urlopen(f"{base_url}/api/history") as response:
        assert response.status == 200
        history = json.loads(response.read())
    assert history["interval_seconds"] == 5.0
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
