"""Fake curses screen for testing TUI rendering without a real terminal.

Tracks all writes by coordinate and flags out-of-bounds attempts as errors.
"""

from __future__ import annotations


class FakeScreen:
    def __init__(self, height: int = 24, width: int = 80, keys: list[int] | None = None) -> None:
        self.height = height
        self.width = width
        self.keys = list(keys or [])
        self.writes: list[tuple[int, int, str, int | None]] = []
        self.out_of_bounds: list[tuple[int, int, str]] = []
        self.erased = False
        self.noutrefreshed = False
        self.timeout_value: int | None = None
        self.keypad_value: bool | None = None

    def getch(self) -> int:
        if self.keys:
            return self.keys.pop(0)
        return -1

    def getmaxyx(self) -> tuple[int, int]:
        return self.height, self.width

    def addnstr(self, y: int, x: int, text: str, length: int, attr: int | None = None) -> None:
        if y < 0 or y >= self.height or x < 0 or x >= self.width:
            self.out_of_bounds.append((y, x, text[:length]))
            return
        self.writes.append((y, x, text[:length], attr))

    def erase(self) -> None:
        self.erased = True
        self.writes.clear()

    def noutrefresh(self) -> None:
        self.noutrefreshed = True

    def nodelay(self, value: bool) -> None:
        pass

    def keypad(self, value: bool) -> None:
        self.keypad_value = value

    def timeout(self, value: int) -> None:
        self.timeout_value = value

    def resize(self, height: int, width: int) -> None:
        self.height = height
        self.width = width

    def text_at(self, y: int) -> str:
        """Return concatenated text written to row y (for assertions)."""
        parts = [(x, text) for wy, x, text, _ in self.writes if wy == y]
        parts.sort(key=lambda p: p[0])
        return "".join(text for _, text in parts)

    def has_text(self, substring: str) -> bool:
        """Check if any row contains the substring."""
        return any(substring in self.text_at(row) for row in range(self.height))
