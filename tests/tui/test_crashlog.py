"""Tests for one-shot crash logging."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

from rk3562deb_dashboard.tui.crashlog import _write_crash, install_crash_handler


def test_write_crash_creates_file_with_traceback(tmp_path: Path) -> None:
    try:
        raise ValueError("boom from test")
    except ValueError as exc:
        path = _write_crash(tmp_path / "rk-tui", type(exc), exc, exc.__traceback__, "MainThread")

    assert path is not None
    text = path.read_text(encoding="utf-8")
    assert "ValueError: boom from test" in text
    assert "MainThread" in text
    assert "test_crashlog.py" in text


def test_write_crash_returns_none_on_unwritable_dir(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")

    path = _write_crash(blocker / "sub", ValueError, ValueError("x"), None, "MainThread")

    assert path is None


def test_thread_hook_writes_crash_file(tmp_path: Path) -> None:
    prev_sys_hook = sys.excepthook
    prev_thread_hook = threading.excepthook
    try:
        # Quiet previous hooks so the chained call does not spam stderr.
        threading.excepthook = lambda args: None
        install_crash_handler(crash_dir=tmp_path)

        def crash() -> None:
            raise RuntimeError("worker thread crash")

        worker = threading.Thread(target=crash, name="dashboard-sampler")
        worker.start()
        worker.join()
    finally:
        sys.excepthook = prev_sys_hook
        threading.excepthook = prev_thread_hook

    text = (tmp_path / "crash.log").read_text(encoding="utf-8")
    assert "RuntimeError: worker thread crash" in text
    assert "dashboard-sampler" in text


def test_sys_hook_skips_keyboard_interrupt(tmp_path: Path) -> None:
    prev_sys_hook = sys.excepthook
    prev_thread_hook = threading.excepthook
    chained: list[type[BaseException]] = []
    try:
        sys.excepthook = lambda exc_type, exc, tb: chained.append(exc_type)
        install_crash_handler(crash_dir=tmp_path)
        sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
    finally:
        sys.excepthook = prev_sys_hook
        threading.excepthook = prev_thread_hook

    assert chained == [KeyboardInterrupt]
    assert not (tmp_path / "crash.log").exists()
