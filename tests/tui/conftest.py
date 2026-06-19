"""Shared fixtures for TUI tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from rk3562deb_dashboard.collectors import CollectorState, collect_snapshot
from rk3562deb_dashboard.models import DashboardSnapshot
from rk3562deb_dashboard.sampler import DashboardSampler
from rk3562deb_dashboard.tui.app import RKDashboardTui

from .fake_screen import FakeScreen

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture()
def healthy_snapshot() -> DashboardSnapshot:
    state = CollectorState()
    return collect_snapshot(state, FIXTURES / "healthy_rk3562")


@pytest.fixture()
def partial_snapshot() -> DashboardSnapshot:
    state = CollectorState()
    return collect_snapshot(state, FIXTURES / "partial_sysfs")


def make_app(
    fixture_root: Path = FIXTURES / "healthy_rk3562",
    height: int = 40,
    width: int = 140,
    keys: list[int] | None = None,
    once: bool = True,
    no_color: bool = True,
    ascii_only: bool = True,
) -> tuple[RKDashboardTui, FakeScreen]:
    """Create an app wired to a fake screen for testing."""
    stop_keys = keys or [ord("q")]
    sampler = DashboardSampler(root=fixture_root, interval=2.0)
    app = RKDashboardTui(
        sampler=sampler,
        interval=2.0,
        once=once,
        no_color=no_color,
        ascii_only=ascii_only,
    )
    screen = FakeScreen(height=height, width=width, keys=stop_keys)
    app._stdscr = screen  # type: ignore[assignment]
    app._running = True
    # Override refresh to skip curses.doupdate() which needs a real terminal
    app.refresh = lambda: screen.noutrefresh() if screen else None  # type: ignore[assignment]
    app.on_start()
    app.update()
    app.draw()
    return app, screen
