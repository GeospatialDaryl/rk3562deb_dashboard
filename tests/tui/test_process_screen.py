"""Tests for the dedicated process detail screen."""

from __future__ import annotations

from rk3562deb_dashboard.tui.state import ProcessSort, ScreenId

from .conftest import make_app


def test_process_screen_renders_header() -> None:
    app, screen = make_app(height=40, width=140)
    app._state.active_screen = ScreenId.PROCESSES
    app.draw()
    assert screen.has_text("Processes:")
    assert screen.has_text("sort: CPU%")


def test_process_screen_renders_table_header() -> None:
    app, screen = make_app(height=40, width=140)
    app._state.active_screen = ScreenId.PROCESSES
    app.draw()
    assert screen.has_text("PID")
    assert screen.has_text("CPU%")
    assert screen.has_text("RSS")
    assert screen.has_text("Name")


def test_process_screen_renders_entries() -> None:
    app, screen = make_app(height=40, width=140)
    app._state.active_screen = ScreenId.PROCESSES
    app.draw()
    assert screen.has_text("chromium")


def test_process_screen_no_out_of_bounds() -> None:
    app, screen = make_app(height=40, width=140)
    app._state.active_screen = ScreenId.PROCESSES
    app.draw()
    assert screen.out_of_bounds == []


def test_sort_cycle_key() -> None:
    app, screen = make_app()
    assert app._state.selected_process_sort == ProcessSort.CPU
    app._cycle_process_sort(ord("s"))
    assert app._state.selected_process_sort == ProcessSort.MEMORY
    app._cycle_process_sort(ord("s"))
    assert app._state.selected_process_sort == ProcessSort.PID
    app._cycle_process_sort(ord("s"))
    assert app._state.selected_process_sort == ProcessSort.NAME
    app._cycle_process_sort(ord("s"))
    assert app._state.selected_process_sort == ProcessSort.CPU


def test_sort_by_memory() -> None:
    app, screen = make_app(height=40, width=140)
    app._state.active_screen = ScreenId.PROCESSES
    app._state.selected_process_sort = ProcessSort.MEMORY
    app.draw()
    assert screen.has_text("sort: MEM")


def test_process_screen_shows_command_column() -> None:
    app, screen = make_app(height=40, width=140)
    app._state.active_screen = ScreenId.PROCESSES
    app.draw()
    assert screen.has_text("Command")


def test_overview_shows_cpu_percent() -> None:
    app, screen = make_app(height=40, width=140)
    assert screen.has_text("CPU%")
