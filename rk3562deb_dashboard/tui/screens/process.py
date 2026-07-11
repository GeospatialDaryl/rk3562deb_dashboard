"""Full-screen process detail view."""

from __future__ import annotations

import curses
from typing import TYPE_CHECKING

from ...models import ProcessInfo, ProcessMetrics
from ..formatting import format_bytes
from ..state import ProcessSort

if TYPE_CHECKING:
    from ..app import RKDashboardTui


SORT_LABELS: dict[ProcessSort, str] = {
    ProcessSort.CPU: "CPU%",
    ProcessSort.MEMORY: "MEM",
    ProcessSort.PID: "PID",
    ProcessSort.NAME: "NAME",
}

SORT_CYCLE = [ProcessSort.CPU, ProcessSort.MEMORY, ProcessSort.PID, ProcessSort.NAME]


def draw_process_screen(
    app: RKDashboardTui,
    y: int,
    width: int,
    height: int,
) -> None:
    snap = app._snapshot
    if snap is None:
        app.center_text(height // 2, "Collecting initial data...", curses.A_BOLD)
        return

    proc_mv = snap.processes
    if not proc_mv.is_available or proc_mv.value is None:
        label = f"Processes: {app._state_label(proc_mv.state)}"
        app.addstr(y, 0, label[:width], app._attr_unavailable())
        return

    procs = proc_mv.value
    sort_key = app._state.selected_process_sort
    entries = _sorted_entries(procs, sort_key)

    sort_label = SORT_LABELS.get(sort_key, "?")
    title = f"Processes: {procs.count}  [sort: {sort_label}  s=cycle]"
    state_parts = [f"{k}={v}" for k, v in sorted(procs.states.items())]
    if state_parts:
        title += f"  ({', '.join(state_parts)})"
    app.addstr(y, 0, title[:width], app._attr_header())
    y += 1

    if y >= height - 1:
        return

    col_pid = 7
    col_cpu = 7
    col_mem = 10
    col_st = 3
    col_name = 20
    fixed = col_pid + col_cpu + col_mem + col_st + col_name + 12
    col_cmd = max(0, width - fixed)

    hdr = (
        f"  {'PID':>{col_pid}s}"
        f"  {'CPU%':>{col_cpu}s}"
        f"  {'RSS':>{col_mem}s}"
        f"  {'S':>{col_st}s}"
        f"  {'Name':<{col_name}s}"
    )
    if col_cmd > 5:
        hdr += f"  {'Command':<{col_cmd}s}"
    app.addstr(y, 0, hdr[:width], curses.A_UNDERLINE)
    y += 1

    available = height - y - 1
    for proc in entries[:available]:
        rss = format_bytes(proc.rss_bytes)
        cpu_str = f"{proc.cpu_percent:.1f}"
        line = (
            f"  {proc.pid:>{col_pid}d}"
            f"  {cpu_str:>{col_cpu}s}"
            f"  {rss:>{col_mem}s}"
            f"  {proc.state:>{col_st}s}"
            f"  {proc.name:<{col_name}s}"
        )
        if col_cmd > 5:
            cmd = proc.cmdline[:col_cmd] if proc.cmdline else ""
            line += f"  {cmd}"

        attr = 0
        if proc.cpu_percent >= 80:
            attr = app._attr_critical()
        elif proc.cpu_percent >= 40:
            attr = app._attr_warn()

        app.addstr(y, 0, line[:width], attr)
        y += 1


def _sorted_entries(procs: ProcessMetrics, sort_key: ProcessSort) -> list[ProcessInfo]:
    entries = list(procs.top_memory)
    if sort_key == ProcessSort.CPU:
        entries.sort(key=lambda p: p.cpu_percent, reverse=True)
    elif sort_key == ProcessSort.MEMORY:
        entries.sort(key=lambda p: p.rss_bytes, reverse=True)
    elif sort_key == ProcessSort.PID:
        entries.sort(key=lambda p: p.pid)
    elif sort_key == ProcessSort.NAME:
        entries.sort(key=lambda p: p.name.lower())
    return entries
