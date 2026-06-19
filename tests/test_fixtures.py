"""Integration tests that run collect_snapshot against static fixture trees."""

from __future__ import annotations

from pathlib import Path

from rk3562deb_dashboard.collectors import CollectorState, collect_snapshot
from rk3562deb_dashboard.sampler import make_history_point
from rk3562deb_dashboard.serialization import snapshot_to_dict

FIXTURES = Path(__file__).parent / "fixtures"


def test_healthy_rk3562_snapshot() -> None:
    root = FIXTURES / "healthy_rk3562"
    state = CollectorState()
    snap = collect_snapshot(state, root)

    assert snap.host.model == "Rockchip RK3562 Tablet"
    assert snap.host.uptime_seconds == 86400.5
    assert snap.host.load == (0.45, 0.3, 0.25)

    assert snap.cpu.is_available
    cpu = snap.cpu.value
    assert cpu is not None
    assert len(cpu.cores) == 4
    assert cpu.cores[0].frequency_khz == 1800000

    assert snap.memory.is_available
    mem = snap.memory.value
    assert mem is not None
    assert mem.total_bytes == 4096000 * 1024

    assert snap.thermal.is_available
    thermal = snap.thermal.value
    assert thermal is not None
    assert len(thermal) == 2
    assert thermal[0].name == "soc-thermal"
    assert thermal[0].temperature_c == 42.5

    assert snap.power.is_available
    power = snap.power.value
    assert power is not None
    assert len(power.supplies) == 2
    assert power.supplies[0].capacity_percent == 76

    assert snap.npu.is_available
    npu = snap.npu.value
    assert npu is not None
    assert npu.driver_version == "0.9.8"
    assert len(npu.devices) == 1
    assert npu.devices[0].load_percent == 15

    assert snap.rockchip.is_available
    rk = snap.rockchip.value
    assert rk is not None
    assert len(rk.storage) == 2


def test_healthy_rk3562_serializes_to_dict() -> None:
    root = FIXTURES / "healthy_rk3562"
    state = CollectorState()
    snap = collect_snapshot(state, root)
    d = snapshot_to_dict(snap)

    assert "timestamp" in d
    assert d["host"]["model"] == "Rockchip RK3562 Tablet"
    assert d["cpu"]["total"]["usage_percent"] == 0.0
    assert d["memory"]["total_bytes"] == 4096000 * 1024
    assert len(d["thermal"]) == 2
    assert d["npu"]["driver_version"] == "0.9.8"


def test_healthy_rk3562_history_point() -> None:
    root = FIXTURES / "healthy_rk3562"
    state = CollectorState()
    snap = collect_snapshot(state, root)
    hp = make_history_point(snap)

    assert hp.cpu_percent is not None
    assert hp.memory_percent is not None
    assert hp.max_temperature_c == 42.5


def test_no_npu_fixture() -> None:
    root = FIXTURES / "no_npu"
    state = CollectorState()
    snap = collect_snapshot(state, root)

    assert snap.npu.is_available
    npu = snap.npu.value
    assert npu is not None
    assert npu.driver_version is None
    assert npu.devices == ()


def test_battery_absent_fixture() -> None:
    root = FIXTURES / "battery_absent"
    state = CollectorState()
    snap = collect_snapshot(state, root)

    assert snap.power.is_available
    power = snap.power.value
    assert power is not None
    assert power.supplies == ()


def test_partial_sysfs_fixture() -> None:
    root = FIXTURES / "partial_sysfs"
    state = CollectorState()
    snap = collect_snapshot(state, root)

    assert snap.cpu.is_available
    cpu = snap.cpu.value
    assert cpu is not None
    assert cpu.cores[0].frequency_khz is None

    assert snap.thermal.is_available
    thermal = snap.thermal.value
    assert thermal is not None
    assert len(thermal) == 0


def test_malformed_metrics_fixture() -> None:
    root = FIXTURES / "malformed_metrics"
    state = CollectorState()
    snap = collect_snapshot(state, root)

    assert snap.memory.is_available
    mem = snap.memory.value
    assert mem is not None
    assert mem.total_bytes == 0

    assert snap.thermal.is_available
    thermal = snap.thermal.value
    assert thermal is not None
    assert thermal[0].temperature_c is None

    assert snap.npu.is_available
    npu = snap.npu.value
    assert npu is not None
    assert npu.devices[0].load_percent is None
    assert npu.devices[0].frequency_hz is None
