"""Tests for sparkline widget rendering."""

from __future__ import annotations

from rk3562deb_dashboard.tui.widgets.sparkline import render_sparkline


def test_full_history_renders_all() -> None:
    values = [0.0, 25.0, 50.0, 75.0, 100.0]
    result = render_sparkline(values, width=5, max_val=100.0)
    assert len(result) == 5
    assert result[0] == " "  # 0%
    assert result[-1] == "█"  # 100%


def test_partial_history_pads_left() -> None:
    values = [50.0, 100.0]
    result = render_sparkline(values, width=5, max_val=100.0)
    assert len(result) == 5
    # First 3 should be missing markers
    assert "—" in result[:3]


def test_empty_history() -> None:
    result = render_sparkline([], width=5)
    assert len(result) == 5
    assert all(c == "—" for c in result)


def test_missing_values_show_dash() -> None:
    values: list[float | None] = [10.0, None, 30.0, None, 50.0]
    result = render_sparkline(values, width=5, max_val=50.0)
    assert len(result) == 5
    assert result[1] == "—"
    assert result[3] == "—"


def test_ascii_mode() -> None:
    values = [0.0, 50.0, 100.0]
    result = render_sparkline(values, width=3, max_val=100.0, ascii_only=True)
    assert len(result) == 3
    assert "—" not in result  # ASCII uses - for missing
    assert "█" not in result  # No unicode


def test_ascii_missing_values() -> None:
    values: list[float | None] = [None, 50.0, None]
    result = render_sparkline(
        values, width=3, max_val=100.0, ascii_only=True,
    )
    assert result[0] == "-"
    assert result[2] == "-"


def test_zero_width_returns_empty() -> None:
    assert render_sparkline([1.0, 2.0], width=0) == ""


def test_all_same_values() -> None:
    values = [50.0] * 10
    result = render_sparkline(values, width=10, max_val=100.0)
    assert len(result) == 10
    assert all(c == result[0] for c in result)


def test_truncates_to_width() -> None:
    values = list(range(20))
    result = render_sparkline(
        [float(v) for v in values], width=10, max_val=19.0,
    )
    assert len(result) == 10


def test_auto_max_val() -> None:
    values = [10.0, 20.0, 30.0]
    result = render_sparkline(values, width=3)
    assert len(result) == 3
    assert result[-1] == "█"  # 30 is max
