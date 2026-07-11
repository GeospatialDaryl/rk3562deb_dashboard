"""System metrics collectors for the RK3562 Debian dashboard.

This subpackage provides typed, read-only collectors for each metric domain.
All reads are best-effort: missing kernel interfaces produce structured
availability states instead of hard failures.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from ..models import DashboardSnapshot
from .base import ROOT
from .cpu import CpuState, collect_cpu
from .host import collect_host
from .memory import collect_memory, collect_swap
from .network import NetworkState, collect_network
from .npu import collect_npu
from .power import collect_power
from .process import ProcessState, collect_processes
from .rockchip import collect_rockchip
from .storage import StorageState, collect_block_io, collect_disks
from .thermal import collect_thermal


@dataclass(slots=True)
class CollectorState:
    """Mutable state needed to calculate deltas between samples."""

    cpu: CpuState = field(default_factory=CpuState)
    storage: StorageState = field(default_factory=StorageState)
    network: NetworkState = field(default_factory=NetworkState)
    process: ProcessState = field(default_factory=ProcessState)
    timestamp: float = field(default_factory=time.monotonic)


def collect_snapshot(
    state: CollectorState | None = None, root: Path = ROOT
) -> DashboardSnapshot:
    state = state or CollectorState()
    now = time.monotonic()
    interval = max(0.001, now - state.timestamp)

    snapshot = DashboardSnapshot(
        captured_at=time.time(),
        monotonic_seconds=now,
        host=collect_host(root),
        cpu=collect_cpu(state.cpu, root),
        memory=collect_memory(root),
        swap=collect_swap(root),
        processes=collect_processes(root, state.process),
        disks=collect_disks(state.storage, interval, root),
        block_io=collect_block_io(state.storage, interval, root),
        network=collect_network(state.network, interval, root),
        thermal=collect_thermal(root),
        power=collect_power(root),
        npu=collect_npu(root),
        rockchip=collect_rockchip(root),
    )
    state.timestamp = now
    return snapshot


__all__ = [
    "CollectorState",
    "collect_snapshot",
    "collect_cpu",
    "collect_host",
    "collect_memory",
    "collect_swap",
    "collect_processes",
    "collect_disks",
    "collect_block_io",
    "collect_network",
    "collect_thermal",
    "collect_power",
    "collect_npu",
    "collect_rockchip",
]
