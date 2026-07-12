"""Snapshot orchestration and bounded in-memory history.

DashboardSampler owns the collector state and produces typed snapshots.
Both the HTTP server and the future TUI consume it directly.
"""

from __future__ import annotations

import threading
from collections import deque
from pathlib import Path

from .collectors import CollectorState, collect_snapshot
from .models import DashboardSnapshot, HistoryPoint

SAMPLE_INTERVAL_SECONDS = 5.0
HISTORY_SIZE = 180  # 15 minutes at the default interval


def make_history_point(snapshot: DashboardSnapshot) -> HistoryPoint:
    thermal = snapshot.thermal.value
    temps = (
        [z.temperature_c for z in thermal if z.temperature_c is not None]
        if thermal
        else []
    )
    block_io = snapshot.block_io.value
    sd_write = emmc_write = None
    if block_io:
        for device in block_io:
            if device.kind == "SD" and sd_write is None:
                sd_write = device.write_bytes_per_sec
            elif device.kind == "MMC" and emmc_write is None:
                emmc_write = device.write_bytes_per_sec
    cpu = snapshot.cpu.value
    mem = snapshot.memory.value
    return HistoryPoint(
        monotonic_seconds=snapshot.monotonic_seconds,
        wall_time=snapshot.captured_at,
        cpu_percent=cpu.usage_percent if cpu else None,
        memory_percent=mem.usage_percent if mem else None,
        max_temperature_c=max(temps) if temps else None,
        sd_write_bytes_per_sec=sd_write,
        emmc_write_bytes_per_sec=emmc_write,
    )


class DashboardSampler:
    """Periodic collector that maintains typed snapshots and history.

    Thread-safe: the background sampler thread writes; callers read through
    snapshot() and history_points() which hold the lock briefly.
    """

    def __init__(
        self,
        root: Path = Path("/"),
        interval: float = SAMPLE_INTERVAL_SECONDS,
        history_size: int = HISTORY_SIZE,
    ) -> None:
        self.root = root
        self.interval = interval
        self._state = CollectorState()
        self._lock = threading.Lock()
        self._history: deque[HistoryPoint] = deque(maxlen=history_size)
        self._latest = collect_snapshot(self._state, root)
        self._history.append(make_history_point(self._latest))
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._sample_loop, name="dashboard-sampler", daemon=True
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5)

    def sample(self) -> DashboardSnapshot:
        with self._lock:
            return self._latest

    def sample_now(self) -> DashboardSnapshot:
        snap = collect_snapshot(self._state, self.root)
        hp = make_history_point(snap)
        with self._lock:
            self._latest = snap
            self._history.append(hp)
        return snap

    def history(self) -> list[HistoryPoint]:
        with self._lock:
            return list(self._history)

    def _sample_loop(self) -> None:
        while not self._stop.wait(self.interval):
            snap = collect_snapshot(self._state, self.root)
            hp = make_history_point(snap)
            with self._lock:
                self._latest = snap
                self._history.append(hp)
