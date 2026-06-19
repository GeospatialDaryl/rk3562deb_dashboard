from __future__ import annotations

from pathlib import Path

from ..models import MetricValue, ThermalZoneMetrics
from .base import ROOT, glob_sorted, read_int, read_text, relative_sys_path


def collect_thermal(root: Path = ROOT) -> MetricValue[tuple[ThermalZoneMetrics, ...]]:
    zones: list[ThermalZoneMetrics] = []
    for zone in glob_sorted("/sys/class/thermal/thermal_zone*", root):
        rel = Path("/") / zone.relative_to(root)
        temp_milli = read_int(rel / "temp", root)
        zones.append(ThermalZoneMetrics(
            name=read_text(rel / "type", root) or zone.name,
            temperature_c=round(temp_milli / 1000.0, 1) if temp_milli is not None else None,
            path=relative_sys_path(zone, root),
        ))
    return MetricValue.available(tuple(zones))
