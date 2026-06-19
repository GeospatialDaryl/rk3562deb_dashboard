"""Tests for compact mode and minimum-size guard rendering."""

from __future__ import annotations

from .conftest import make_app


def test_too_small_shows_safe_message() -> None:
    app, screen = make_app(height=20, width=60)
    assert screen.has_text("Terminal too small")
    assert screen.has_text("60x20")
    assert screen.has_text("80x24")
    assert screen.out_of_bounds == []


def test_too_small_narrow_width() -> None:
    app, screen = make_app(height=24, width=40)
    assert screen.has_text("Terminal too small")
    assert screen.out_of_bounds == []


def test_compact_80x24_renders_without_crash() -> None:
    app, screen = make_app(height=24, width=80)
    assert screen.has_text("samwise")
    assert screen.out_of_bounds == []


def test_compact_hides_per_core_cpu() -> None:
    app, screen = make_app(height=24, width=80)
    # In compact mode, per-core CPU lines should not appear
    assert not screen.has_text("cpu0:")


def test_medium_100x30_renders_without_crash() -> None:
    app, screen = make_app(height=30, width=100)
    assert screen.has_text("samwise")
    assert screen.out_of_bounds == []


def test_no_out_of_bounds_at_minimum_size() -> None:
    app, screen = make_app(height=24, width=80)
    assert screen.out_of_bounds == [], f"Out of bounds: {screen.out_of_bounds}"


def test_help_overlay_at_80x24() -> None:
    app, screen = make_app(height=24, width=80)
    app._state.show_help = True
    screen.erased = False
    screen.writes.clear()
    app.draw()
    assert screen.has_text("Keyboard Help")
    assert screen.has_text("q / Q / Ctrl-C")
    assert screen.out_of_bounds == []


def test_forced_compact_at_full_size() -> None:
    app, screen = make_app(height=40, width=140)
    app._force_compact = True
    screen.writes.clear()
    app.draw()
    # Should not show per-core details even at full size
    assert not screen.has_text("cpu0:")


def test_paused_shows_in_status_line() -> None:
    app, screen = make_app(height=24, width=80)
    app._state.is_paused = True
    screen.writes.clear()
    app.draw()
    assert screen.has_text("PAUSED")
