"""Shared filesystem helpers for collectors.

All reads are best-effort: missing kernel interfaces produce structured
unavailable states instead of hard failures.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path("/")


def read_text(path: Path, root: Path = ROOT) -> str | None:
    try:
        return (root / path.relative_to("/")).read_text(encoding="utf-8", errors="replace").strip()
    except (FileNotFoundError, PermissionError, OSError):
        return None


def read_int(path: Path, root: Path = ROOT) -> int | None:
    text = read_text(path, root)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def glob_sorted(pattern: str, root: Path = ROOT) -> list[Path]:
    return sorted(root.glob(pattern.lstrip("/")))


def relative_sys_path(path: Path, root: Path = ROOT) -> str:
    try:
        return "/" + str(path.relative_to(root))
    except ValueError:
        return str(path)


def percent(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(max(0.0, min(100.0, (numerator / denominator) * 100.0)), 1)


def clean_dt_string(value: str | None) -> str | None:
    if not value:
        return None
    return value.replace("\x00", ", ").strip(" ,")


def parse_meminfo(root: Path = ROOT) -> dict[str, int]:
    meminfo = read_text(Path("/proc/meminfo"), root) or ""
    parsed: dict[str, int] = {}
    for line in meminfo.splitlines():
        match = re.match(r"^(\w+):\s+(\d+)", line)
        if match:
            parsed[match.group(1)] = int(match.group(2)) * 1024
    return parsed
