"""Tests for responsive layout breakpoints."""

from __future__ import annotations

from rk3562deb_dashboard.tui.layout import LayoutMode, compute_layout


def test_full_layout() -> None:
    layout = compute_layout(50, 160)
    assert layout.mode == LayoutMode.FULL
    assert layout.content_height == 49


def test_medium_layout() -> None:
    layout = compute_layout(35, 120)
    assert layout.mode == LayoutMode.MEDIUM


def test_compact_layout() -> None:
    layout = compute_layout(24, 80)
    assert layout.mode == LayoutMode.COMPACT


def test_too_small_width() -> None:
    layout = compute_layout(24, 79)
    assert layout.mode == LayoutMode.TOO_SMALL


def test_too_small_height() -> None:
    layout = compute_layout(23, 80)
    assert layout.mode == LayoutMode.TOO_SMALL


def test_too_small_both() -> None:
    layout = compute_layout(10, 40)
    assert layout.mode == LayoutMode.TOO_SMALL
    assert layout.content_height == 9


def test_medium_boundary_exact() -> None:
    layout = compute_layout(30, 100)
    assert layout.mode == LayoutMode.MEDIUM


def test_full_boundary_exact() -> None:
    layout = compute_layout(40, 140)
    assert layout.mode == LayoutMode.FULL
