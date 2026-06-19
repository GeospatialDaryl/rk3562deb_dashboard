from __future__ import annotations

from pathlib import Path

from ..models import MemoryMetrics, MetricValue, SwapMetrics
from .base import ROOT, parse_meminfo, percent


def collect_memory(root: Path = ROOT) -> MetricValue[MemoryMetrics]:
    mem = parse_meminfo(root)
    total = mem.get("MemTotal", 0)
    available = mem.get("MemAvailable", 0)
    used = max(0, total - available)
    return MetricValue.available(MemoryMetrics(
        total_bytes=total,
        available_bytes=available,
        used_bytes=used,
        usage_percent=percent(used, total),
        buffers_bytes=mem.get("Buffers", 0),
        cached_bytes=mem.get("Cached", 0) + mem.get("SReclaimable", 0),
    ))


def collect_swap(root: Path = ROOT) -> MetricValue[SwapMetrics]:
    mem = parse_meminfo(root)
    total = mem.get("SwapTotal", 0)
    free = mem.get("SwapFree", 0)
    used = max(0, total - free)
    return MetricValue.available(SwapMetrics(
        total_bytes=total,
        used_bytes=used,
        usage_percent=percent(used, total),
    ))
