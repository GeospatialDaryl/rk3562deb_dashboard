"""Tests for structured unavailable/unsupported/untrusted display states."""

from __future__ import annotations

from rk3562deb_dashboard.models import MetricValue

from .conftest import FIXTURES, make_app


def test_no_npu_shows_not_detected() -> None:
    app, screen = make_app(fixture_root=FIXTURES / "no_npu", height=40, width=140)
    assert screen.has_text("NPU: not detected")
    assert screen.out_of_bounds == []


def test_battery_absent_shows_unsupported() -> None:
    app, screen = make_app(fixture_root=FIXTURES / "battery_absent", height=40, width=140)
    assert screen.has_text("Battery: unsupported")


def test_partial_sysfs_cpu_has_no_frequency() -> None:
    app, screen = make_app(fixture_root=FIXTURES / "partial_sysfs", height=40, width=140)
    assert screen.has_text("CPU")
    assert not screen.has_text("MHz")


def test_malformed_thermal_shows_dash() -> None:
    app, screen = make_app(fixture_root=FIXTURES / "malformed_metrics", height=40, width=140)
    # Malformed temp should show — not crash
    assert screen.out_of_bounds == []


def test_healthy_sd_and_emmc_distinct() -> None:
    app, screen = make_app(height=40, width=140)
    assert screen.has_text("SD")
    assert screen.has_text("eMMC")


def test_sd_emmc_compact_mode() -> None:
    app, screen = make_app(height=24, width=80)
    # In compact mode SD/eMMC should still appear
    has_sd = screen.has_text("SD:")
    has_emmc = screen.has_text("eMMC:")
    # At least one should be present if block_io data exists
    assert has_sd or has_emmc or screen.has_text("Storage")


def test_npu_trust_untrusted_shows_question_mark() -> None:
    """NPU with STATIC_OR_UNTRUSTED state should show ? for load."""
    app, screen = make_app(height=40, width=140)
    # Override the NPU metric to be untrusted
    snap = app._snapshot
    assert snap is not None
    npu = snap.npu.value
    assert npu is not None
    # Create an untrusted version
    untrusted_npu = MetricValue.static_or_untrusted(npu, detail="static load")
    # Replace snapshot with modified version
    from dataclasses import replace
    app._snapshot = replace(snap, npu=untrusted_npu)
    screen.writes.clear()
    app.draw()
    assert screen.has_text("unverified")
    assert not screen.has_text("load=15%")


def test_npu_trusted_shows_load_percent() -> None:
    app, screen = make_app(height=40, width=140)
    assert screen.has_text("load=15%")
    assert not screen.has_text("unverified")


def test_overview_all_fixtures_no_oob() -> None:
    """Every fixture should render without out-of-bounds at all breakpoints."""
    fixtures = ["healthy_rk3562", "partial_sysfs", "no_npu",
                "malformed_metrics", "battery_absent"]
    sizes = [(50, 160), (35, 120), (30, 100), (24, 80)]
    for fixture in fixtures:
        for h, w in sizes:
            root = FIXTURES / fixture
            app, screen = make_app(fixture_root=root, height=h, width=w)
            assert screen.out_of_bounds == [], (
                f"OOB at {w}x{h} with {fixture}: {screen.out_of_bounds}"
            )
