from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..models import (
    BlockIoDevice,
    DiskMetrics,
    MetricValue,
    StorageIdentity,
)
from .base import ROOT, glob_sorted, percent, read_int, read_text


@dataclass(slots=True)
class StorageState:
    disks: dict[str, tuple[int, int]] = field(default_factory=dict)
    blocks: dict[str, tuple[int, int]] = field(default_factory=dict)


def collect_disks(
    state: StorageState, interval: float, root: Path = ROOT
) -> MetricValue[tuple[DiskMetrics, ...]]:
    mounts = read_text(Path("/proc/self/mountinfo"), root) or ""
    diskstats = _parse_diskstats(root)
    devices_seen: set[str] = set()
    disks: list[DiskMetrics] = []

    for line in mounts.splitlines():
        parts = line.split()
        if len(parts) < 10 or " - " not in line:
            continue
        separator = parts.index("-")
        mount_point = parts[4].replace("\\040", " ")
        fs_type = parts[separator + 1]
        source = parts[separator + 2]
        if not source.startswith("/dev/") or mount_point in devices_seen:
            continue
        devices_seen.add(mount_point)
        usage = _disk_usage(mount_point, root)
        device_name = Path(source).name
        reads, writes = diskstats.get(device_name, (0, 0))
        previous_reads, previous_writes = state.disks.get(mount_point, (reads, writes))
        state.disks[mount_point] = (reads, writes)
        disks.append(DiskMetrics(
            mount=mount_point,
            source=source,
            filesystem=fs_type,
            total_bytes=usage[0],
            used_bytes=usage[1],
            usage_percent=usage[2],
            read_bytes_per_sec=max(0, round((reads - previous_reads) / interval)),
            write_bytes_per_sec=max(0, round((writes - previous_writes) / interval)),
        ))
    return MetricValue.available(tuple(disks))


def collect_block_io(
    state: StorageState, interval: float, root: Path = ROOT
) -> MetricValue[tuple[BlockIoDevice, ...]]:
    diskstats = _parse_diskstats(root)
    devices: list[BlockIoDevice] = []
    for block in glob_sorted("/sys/block/*", root):
        if not block.name.startswith(("mmcblk", "nvme", "sd")):
            continue
        if re.search(r"mmcblk\d+(boot\d+|rpmb)$", block.name):
            continue
        rel = Path("/") / block.relative_to(root)
        reads, writes = diskstats.get(block.name, (0, 0))
        previous_reads, previous_writes = state.blocks.get(block.name, (reads, writes))
        state.blocks[block.name] = (reads, writes)
        devices.append(BlockIoDevice(
            name=block.name,
            kind=read_text(rel / "device/type", root),
            read_bytes_total=reads,
            written_bytes_total=writes,
            read_bytes_per_sec=max(0, round((reads - previous_reads) / interval)),
            write_bytes_per_sec=max(0, round((writes - previous_writes) / interval)),
        ))
    return MetricValue.available(tuple(devices))


def collect_storage_identity(root: Path = ROOT) -> tuple[StorageIdentity, ...]:
    devices: list[StorageIdentity] = []
    for block in glob_sorted("/sys/block/*", root):
        if not block.name.startswith(("mmcblk", "nvme", "sd")):
            continue
        rel = Path("/") / block.relative_to(root)
        devices.append(StorageIdentity(
            name=block.name,
            model=read_text(rel / "device/model", root),
            type=read_text(rel / "queue/rotational", root),
            size_bytes=(read_int(rel / "size", root) or 0) * 512,
            removable=read_int(rel / "removable", root),
        ))
    return tuple(devices)


def _disk_usage(mount_point: str, root: Path = ROOT) -> tuple[int, int, float]:
    path = root / mount_point.lstrip("/")
    try:
        usage = os.statvfs(path)
    except OSError:
        return (0, 0, 0.0)
    total = usage.f_blocks * usage.f_frsize
    free = usage.f_bavail * usage.f_frsize
    used = max(0, total - free)
    return (total, used, percent(used, total))


def _parse_diskstats(root: Path = ROOT) -> dict[str, tuple[int, int]]:
    text = read_text(Path("/proc/diskstats"), root) or ""
    stats: dict[str, tuple[int, int]] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 14:
            continue
        name = parts[2]
        sectors_read = int(parts[5])
        sectors_written = int(parts[9])
        stats[name] = (sectors_read * 512, sectors_written * 512)
    return stats
