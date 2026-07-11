from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..models import MetricValue, ProcessInfo, ProcessMetrics
from .base import ROOT, read_text

MIN_REFRESH_SECONDS = 30.0
"""Full /proc walk is expensive (open+read 3 files per process); nothing
consumes process metrics faster than the web client's poll interval, so
skip recomputing on sampler ticks that fall within this window."""


@dataclass(slots=True)
class ProcessState:
    cpu_times: dict[int, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.monotonic)
    cached: MetricValue[ProcessMetrics] | None = None
    cached_at: float = field(default_factory=lambda: float("-inf"))


def collect_processes(
    root: Path = ROOT, state: ProcessState | None = None,
) -> MetricValue[ProcessMetrics]:
    now_wall = time.monotonic()
    if (
        state is not None
        and state.cached is not None
        and (now_wall - state.cached_at) < MIN_REFRESH_SECONDS
    ):
        return state.cached

    proc_root = root / "proc"
    process_dirs = (
        [p for p in proc_root.iterdir() if p.name.isdigit()]
        if proc_root.exists()
        else []
    )
    states: dict[str, int] = {}
    entries: list[ProcessInfo] = []

    now = time.monotonic()
    interval = max(0.001, now - state.timestamp) if state else 1.0
    new_cpu_times: dict[int, float] = {}

    for proc in process_dirs:
        pid = int(proc.name)
        status = read_text(Path("/proc") / proc.name / "status", root) or ""
        fields = _parse_status(status)
        proc_state = fields.get("State", "?")[:1]
        states[proc_state] = states.get(proc_state, 0) + 1
        rss_kb = _status_kb(fields.get("VmRSS"))

        cpu_percent = 0.0
        stat_text = read_text(Path("/proc") / proc.name / "stat", root)
        if stat_text:
            cpu_ticks = _parse_cpu_ticks(stat_text)
            if cpu_ticks is not None:
                new_cpu_times[pid] = cpu_ticks
                if state and pid in state.cpu_times:
                    delta = cpu_ticks - state.cpu_times[pid]
                    cpu_percent = round(
                        max(0.0, (delta / _clock_ticks()) / interval * 100.0),
                        1,
                    )

        cmdline = ""
        cmdline_raw = read_text(
            Path("/proc") / proc.name / "cmdline", root,
        )
        if cmdline_raw:
            cmdline = cmdline_raw.replace("\x00", " ").strip()

        if rss_kb > 0 or cpu_percent > 0:
            entries.append(ProcessInfo(
                pid=pid,
                name=fields.get("Name", proc.name),
                state=proc_state,
                rss_bytes=rss_kb * 1024,
                cpu_percent=cpu_percent,
                cmdline=cmdline,
            ))

    if state is not None:
        state.cpu_times = new_cpu_times
        state.timestamp = now

    entries.sort(key=lambda item: item.rss_bytes, reverse=True)
    result = MetricValue.available(ProcessMetrics(
        count=len(process_dirs),
        states=states,
        top_memory=tuple(entries[:15]),
    ))
    if state is not None:
        state.cached = result
        state.cached_at = now_wall
    return result


def _parse_status(status: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in status.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            parsed[key] = value.strip()
    return parsed


def _status_kb(value: str | None) -> int:
    if not value:
        return 0
    match = re.match(r"^(\d+)", value)
    return int(match.group(1)) if match else 0


def _parse_cpu_ticks(stat_line: str) -> float | None:
    # /proc/<pid>/stat: skip past comm field (may contain spaces/parens)
    close_paren = stat_line.rfind(")")
    if close_paren < 0:
        return None
    fields = stat_line[close_paren + 2:].split()
    if len(fields) < 12:
        return None
    try:
        utime = int(fields[11])
        stime = int(fields[12])
        return float(utime + stime)
    except (ValueError, IndexError):
        return None


_cached_clock_ticks: float | None = None


def _clock_ticks() -> float:
    global _cached_clock_ticks  # noqa: PLW0603
    if _cached_clock_ticks is None:
        try:
            import os
            _cached_clock_ticks = float(os.sysconf("SC_CLK_TCK"))
        except (ValueError, OSError, AttributeError):
            _cached_clock_ticks = 100.0
    return _cached_clock_ticks
