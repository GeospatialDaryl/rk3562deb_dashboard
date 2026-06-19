"""Tests for keyboard bindings and state transitions."""

from __future__ import annotations

import curses

from rk3562deb_dashboard.tui.state import ScreenId, TuiState

from .conftest import make_app


def test_help_toggle() -> None:
    app, screen = make_app()
    assert app._state.show_help is False
    app._toggle_help(ord("?"))
    assert app._state.show_help is True
    app._toggle_help(ord("?"))
    assert app._state.show_help is False


def test_pause_toggle() -> None:
    app, screen = make_app()
    assert app._state.is_paused is False
    app._toggle_pause(ord("p"))
    assert app._state.is_paused is True
    app._toggle_pause(ord("p"))
    assert app._state.is_paused is False


def test_screen_switching_by_number() -> None:
    app, screen = make_app()
    app._switch_screen(ord("3"))
    assert app._state.active_screen == ScreenId.STORAGE
    app._switch_screen(ord("7"))
    assert app._state.active_screen == ScreenId.PROCESSES
    app._switch_screen(ord("1"))
    assert app._state.active_screen == ScreenId.OVERVIEW


def test_tab_cycles_screens() -> None:
    app, screen = make_app()
    assert app._state.active_screen == ScreenId.OVERVIEW
    app._next_screen(ord("\t"))
    assert app._state.active_screen == ScreenId.CPU
    app._next_screen(ord("\t"))
    assert app._state.active_screen == ScreenId.STORAGE


def test_shift_tab_cycles_backward() -> None:
    app, screen = make_app()
    app._prev_screen(curses.KEY_BTAB)
    assert app._state.active_screen == ScreenId.PROCESSES


def test_escape_closes_help() -> None:
    app, screen = make_app()
    app._state.show_help = True
    app._on_escape(27)
    assert app._state.show_help is False


def test_escape_returns_to_overview() -> None:
    app, screen = make_app()
    app._state.active_screen = ScreenId.STORAGE
    app._on_escape(27)
    assert app._state.active_screen == ScreenId.OVERVIEW


def test_state_next_wraps_around() -> None:
    state = TuiState()
    state.active_screen = ScreenId.PROCESSES
    state.next_screen()
    assert state.active_screen == ScreenId.OVERVIEW


def test_state_prev_wraps_around() -> None:
    state = TuiState()
    state.active_screen = ScreenId.OVERVIEW
    state.prev_screen()
    assert state.active_screen == ScreenId.PROCESSES


def test_compact_toggle() -> None:
    app, screen = make_app()
    assert app._force_compact is False
    app._toggle_compact(ord("c"))
    assert app._force_compact is True
