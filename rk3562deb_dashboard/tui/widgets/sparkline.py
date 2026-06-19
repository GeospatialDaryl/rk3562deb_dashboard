"""Sparkline rendering for history data."""

from __future__ import annotations

UTF8_BLOCKS = " ▁▂▃▄▅▆▇█"
ASCII_BLOCKS = " _.-:=!|#"
MISSING_CHAR = "—"
MISSING_CHAR_ASCII = "-"


def render_sparkline(
    values: list[float | None],
    width: int,
    min_val: float = 0.0,
    max_val: float | None = None,
    ascii_only: bool = False,
) -> str:
    if width <= 0:
        return ""
    blocks = ASCII_BLOCKS if ascii_only else UTF8_BLOCKS
    missing = MISSING_CHAR_ASCII if ascii_only else MISSING_CHAR

    # Take the most recent `width` values
    display: list[float | None] = values[-width:] if len(values) > width else list(values)
    # Pad with None on the left if not enough data
    if len(display) < width:
        pad: list[float | None] = [None] * (width - len(display))
        display = pad + display

    # Determine scale
    numeric = [v for v in display if v is not None]
    if max_val is None:
        max_val = max(numeric) if numeric else 1.0
    val_range = max_val - min_val
    if val_range <= 0:
        val_range = 1.0

    chars: list[str] = []
    max_idx = len(blocks) - 1
    for v in display:
        if v is None:
            chars.append(missing)
        else:
            normalized = (v - min_val) / val_range
            normalized = max(0.0, min(1.0, normalized))
            idx = int(round(normalized * (max_idx - 1))) + 1 if normalized > 0 else 0
            idx = min(idx, max_idx)
            chars.append(blocks[idx])
    return "".join(chars)
