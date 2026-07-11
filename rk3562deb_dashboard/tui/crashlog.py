"""One-shot crash logging for unhandled exceptions.

The TUI normally writes nothing to disk (SD card endurance on target
devices); this module performs a single write only when the process is
already crashing, so the traceback survives the curses teardown that
otherwise scrolls it away or leaves it only in terminal scrollback.
"""

from __future__ import annotations

import os
import sys
import threading
import traceback
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType


def default_crash_dir() -> Path:
    state_home = os.environ.get("XDG_STATE_HOME", "")
    base = Path(state_home) if state_home else Path.home() / ".local" / "state"
    return base / "rk-tui"


def install_crash_handler(crash_dir: Path | None = None) -> None:
    """Route unhandled exceptions (main and worker threads) to a crash file.

    The previous hooks still run afterwards, so the traceback also reaches
    stderr exactly as before. Best-effort: a failure to write never masks
    the original exception.
    """
    target = crash_dir if crash_dir is not None else default_crash_dir()
    prev_sys_hook = sys.excepthook
    prev_thread_hook = threading.excepthook

    def sys_hook(
        exc_type: type[BaseException],
        exc: BaseException,
        tb: TracebackType | None,
    ) -> None:
        path = None
        if not issubclass(exc_type, KeyboardInterrupt):
            path = _write_crash(target, exc_type, exc, tb, threading.current_thread().name)
        prev_sys_hook(exc_type, exc, tb)
        if path is not None:
            print(f"rk-tui: crash log written to {path}", file=sys.stderr)

    def thread_hook(args: threading.ExceptHookArgs) -> None:
        path = None
        if not issubclass(args.exc_type, (KeyboardInterrupt, SystemExit)):
            thread_name = args.thread.name if args.thread is not None else "unknown"
            path = _write_crash(
                target, args.exc_type, args.exc_value, args.exc_traceback, thread_name,
            )
        prev_thread_hook(args)
        if path is not None:
            print(f"rk-tui: crash log written to {path}", file=sys.stderr)

    sys.excepthook = sys_hook
    threading.excepthook = thread_hook


def _write_crash(
    crash_dir: Path,
    exc_type: type[BaseException],
    exc: BaseException | None,
    tb: TracebackType | None,
    thread_name: str,
) -> Path | None:
    from .. import __version__

    try:
        crash_dir.mkdir(parents=True, exist_ok=True)
        path = crash_dir / "crash.log"
        stamp = datetime.now(UTC).astimezone().isoformat(timespec="seconds")
        body = "".join(traceback.format_exception(exc_type, exc, tb))
        path.write_text(
            f"rk-tui {__version__} crashed at {stamp} in thread {thread_name!r}\n\n{body}",
            encoding="utf-8",
        )
        return path
    except OSError:
        return None
