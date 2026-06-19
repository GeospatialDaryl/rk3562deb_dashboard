"""Responsive layout rules for the TUI dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LayoutMode(StrEnum):
    FULL = "full"          # >= 140x40
    MEDIUM = "medium"      # 100x30 to 139x39
    COMPACT = "compact"    # 80x24 to 99x29
    TOO_SMALL = "too_small"  # < 80x24


MIN_WIDTH = 80
MIN_HEIGHT = 24


@dataclass(frozen=True, slots=True)
class LayoutInfo:
    mode: LayoutMode
    height: int
    width: int
    content_height: int  # height minus status line


def compute_layout(height: int, width: int) -> LayoutInfo:
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        mode = LayoutMode.TOO_SMALL
    elif width >= 140 and height >= 40:
        mode = LayoutMode.FULL
    elif width >= 100 and height >= 30:
        mode = LayoutMode.MEDIUM
    else:
        mode = LayoutMode.COMPACT
    return LayoutInfo(
        mode=mode,
        height=height,
        width=width,
        content_height=max(0, height - 1),
    )
