from __future__ import annotations

from pathlib import Path

from ..models import MetricValue, PowerMetrics, PowerSupply
from .base import ROOT, glob_sorted, read_int, read_text


def collect_power(root: Path = ROOT) -> MetricValue[PowerMetrics]:
    supplies: list[PowerSupply] = []
    for supply in glob_sorted("/sys/class/power_supply/*", root):
        rel = Path("/") / supply.relative_to(root)
        supplies.append(PowerSupply(
            name=supply.name,
            type=read_text(rel / "type", root),
            status=read_text(rel / "status", root),
            voltage_uv=read_int(rel / "voltage_now", root),
            current_ua=read_int(rel / "current_now", root),
            capacity_percent=read_int(rel / "capacity", root),
        ))
    return MetricValue.available(PowerMetrics(supplies=tuple(supplies)))
