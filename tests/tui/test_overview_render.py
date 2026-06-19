"""Tests for overview screen rendering with fixture snapshots."""

from __future__ import annotations

from .conftest import FIXTURES, make_app


def test_overview_renders_host_info() -> None:
    app, screen = make_app(height=40, width=140)
    assert screen.has_text("samwise")
    assert screen.has_text("Rockchip RK3562 Tablet")


def test_overview_renders_cpu_bar() -> None:
    app, screen = make_app(height=40, width=140)
    assert screen.has_text("CPU")


def test_overview_renders_memory() -> None:
    app, screen = make_app(height=40, width=140)
    assert screen.has_text("MEM")


def test_overview_renders_thermal() -> None:
    app, screen = make_app(height=40, width=140)
    assert screen.has_text("Thermal")
    assert screen.has_text("42.5")


def test_overview_renders_storage() -> None:
    app, screen = make_app(height=40, width=140)
    assert screen.has_text("Storage")


def test_overview_renders_network() -> None:
    app, screen = make_app(height=40, width=140)
    assert screen.has_text("wlan0")


def test_overview_renders_battery() -> None:
    app, screen = make_app(height=40, width=140)
    assert screen.has_text("Battery")
    assert screen.has_text("76%")


def test_overview_renders_npu() -> None:
    app, screen = make_app(height=40, width=140)
    assert screen.has_text("NPU")
    assert screen.has_text("0.9.8")


def test_overview_renders_processes() -> None:
    app, screen = make_app(height=40, width=140)
    assert screen.has_text("Processes")
    assert screen.has_text("chromium")


def test_overview_renders_status_line() -> None:
    app, screen = make_app(height=40, width=140)
    assert screen.has_text("[1] Overview")
    assert screen.has_text("?=help")


def test_no_out_of_bounds_writes_full() -> None:
    app, screen = make_app(height=50, width=160)
    assert screen.out_of_bounds == [], f"Out of bounds writes: {screen.out_of_bounds}"


def test_partial_sysfs_renders_without_crash() -> None:
    app, screen = make_app(fixture_root=FIXTURES / "partial_sysfs", height=40, width=140)
    assert screen.has_text("samwise")
    assert screen.out_of_bounds == []


def test_no_npu_renders_without_crash() -> None:
    app, screen = make_app(fixture_root=FIXTURES / "no_npu", height=40, width=140)
    assert screen.out_of_bounds == []


def test_battery_absent_renders_without_crash() -> None:
    app, screen = make_app(fixture_root=FIXTURES / "battery_absent", height=40, width=140)
    assert not screen.has_text("Battery")
    assert screen.out_of_bounds == []


def test_malformed_metrics_renders_without_crash() -> None:
    app, screen = make_app(fixture_root=FIXTURES / "malformed_metrics", height=40, width=140)
    assert screen.out_of_bounds == []
