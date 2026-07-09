from __future__ import annotations

import re
from pathlib import Path

from ..models import MetricValue, NpuDevice, NpuMetrics
from .base import ROOT, glob_sorted, read_int, read_text


def collect_npu(root: Path = ROOT) -> MetricValue[NpuMetrics]:
    devices: list[NpuDevice] = []
    for devfreq in glob_sorted("/sys/class/devfreq/*", root):
        if "npu" not in devfreq.name.lower():
            continue
        rel = Path("/") / devfreq.relative_to(root)
        devices.append(NpuDevice(
            name=devfreq.name,
            load_percent=_effective_load(rel, root),
            frequency_hz=read_int(rel / "cur_freq", root),
            min_hz=read_int(rel / "min_freq", root),
            max_hz=read_int(rel / "max_freq", root),
            governor=read_text(rel / "governor", root),
        ))
    return MetricValue.available(NpuMetrics(
        driver_version=read_text(Path("/sys/module/rknpu/version"), root),
        devices=tuple(devices),
    ))


def _effective_load(devfreq: Path, root: Path) -> int | None:
    # The RK3562 BSP devfreq load node is not live: it latches the last
    # sample taken while the NPU was powered (no polling_interval, zero
    # transitions since boot), so it reads 100% forever after any NPU
    # job. Runtime PM status is authoritative — a suspended device is
    # powered off, hence 0% load. Missing status falls through to the
    # raw devfreq value.
    if read_text(devfreq / "device/power/runtime_status", root) == "suspended":
        return 0
    return _parse_devfreq_load(read_text(devfreq / "load", root))


def _parse_devfreq_load(text: str | None) -> int | None:
    if text is None:
        return None
    match = re.match(r"^(\d+)", text)
    return int(match.group(1)) if match else None
