from __future__ import annotations

import re
from pathlib import Path

from ..models import MetricValue, ProcessInfo, ProcessMetrics
from .base import ROOT, read_text


def collect_processes(root: Path = ROOT) -> MetricValue[ProcessMetrics]:
    proc_root = root / "proc"
    process_dirs = (
        [p for p in proc_root.iterdir() if p.name.isdigit()]
        if proc_root.exists()
        else []
    )
    states: dict[str, int] = {}
    top_memory: list[ProcessInfo] = []

    for proc in process_dirs:
        status = read_text(Path("/proc") / proc.name / "status", root) or ""
        fields = _parse_status(status)
        state = fields.get("State", "?")[:1]
        states[state] = states.get(state, 0) + 1
        rss_kb = _status_kb(fields.get("VmRSS"))
        if rss_kb > 0:
            top_memory.append(ProcessInfo(
                pid=int(proc.name),
                name=fields.get("Name", proc.name),
                state=state,
                rss_bytes=rss_kb * 1024,
            ))

    top_memory.sort(key=lambda item: item.rss_bytes, reverse=True)
    return MetricValue.available(ProcessMetrics(
        count=len(process_dirs),
        states=states,
        top_memory=tuple(top_memory[:8]),
    ))


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
