from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..models import CpuCoreMetrics, CpuMetrics, MetricValue
from .base import ROOT, percent, read_int, read_text


@dataclass(slots=True)
class CpuState:
    previous: dict[str, list[int]] = field(default_factory=dict)


def collect_cpu(state: CpuState, root: Path = ROOT) -> MetricValue[CpuMetrics]:
    stat = read_text(Path("/proc/stat"), root)
    if stat is None:
        return MetricValue.unavailable(detail="cannot read /proc/stat", source="/proc/stat")

    cores: list[CpuCoreMetrics] = []
    aggregate_usage = 0.0
    aggregate_times: tuple[int, ...] = ()
    current: dict[str, list[int]] = {}

    for line in stat.splitlines():
        if not line.startswith("cpu"):
            continue
        name, *values_text = line.split()
        if not values_text or (not name.replace("cpu", "", 1).isdigit() and name != "cpu"):
            continue
        values = [int(v) for v in values_text[:10]]
        current[name] = values
        previous = state.previous.get(name)
        usage = _cpu_usage(previous, values)
        if name == "cpu":
            aggregate_usage = usage
            aggregate_times = tuple(values)
        else:
            core_id = int(name[3:])
            freq = _collect_cpu_frequency(core_id, root)
            cores.append(CpuCoreMetrics(
                core_id=core_id,
                usage_percent=usage,
                **freq,
            ))

    state.previous = current
    return MetricValue.available(CpuMetrics(
        usage_percent=aggregate_usage,
        cores=tuple(cores),
        times=aggregate_times,
    ))


def _cpu_usage(previous: list[int] | None, current: list[int]) -> float:
    if previous is None:
        return 0.0
    total_delta = sum(current) - sum(previous)
    idle_delta = (current[3] + current[4]) - (previous[3] + previous[4])
    return percent(total_delta - idle_delta, total_delta)


def _collect_cpu_frequency(
    core_id: int, root: Path = ROOT
) -> dict[str, int | None]:
    base = Path(f"/sys/devices/system/cpu/cpu{core_id}/cpufreq")
    return {
        "frequency_khz": read_int(base / "scaling_cur_freq", root),
        "min_khz": read_int(base / "scaling_min_freq", root),
        "max_khz": read_int(base / "scaling_max_freq", root),
    }
