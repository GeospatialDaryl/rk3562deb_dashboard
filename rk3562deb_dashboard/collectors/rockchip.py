from __future__ import annotations

from pathlib import Path

from ..models import (
    DevfreqDevice,
    DeviceTreeInfo,
    MetricValue,
    RegulatorInfo,
    RockchipMetrics,
)
from .base import ROOT, clean_dt_string, glob_sorted, read_int, read_text, relative_sys_path
from .storage import collect_storage_identity


def collect_rockchip(root: Path = ROOT) -> MetricValue[RockchipMetrics]:
    return MetricValue.available(RockchipMetrics(
        device_tree=DeviceTreeInfo(
            model=clean_dt_string(read_text(Path("/proc/device-tree/model"), root)),
            compatible=clean_dt_string(read_text(Path("/proc/device-tree/compatible"), root)),
        ),
        devfreq=_collect_devfreq(root),
        regulators=_collect_regulators(root),
        storage=collect_storage_identity(root),
    ))


def _collect_devfreq(root: Path = ROOT) -> tuple[DevfreqDevice, ...]:
    devices: list[DevfreqDevice] = []
    for devfreq in glob_sorted("/sys/class/devfreq/*", root):
        rel = Path("/") / devfreq.relative_to(root)
        devices.append(DevfreqDevice(
            name=devfreq.name,
            frequency_hz=read_int(rel / "cur_freq", root),
            min_hz=read_int(rel / "min_freq", root),
            max_hz=read_int(rel / "max_freq", root),
            governor=read_text(rel / "governor", root),
            path=relative_sys_path(devfreq, root),
        ))
    return tuple(devices)


def _collect_regulators(root: Path = ROOT) -> tuple[RegulatorInfo, ...]:
    regulators: list[RegulatorInfo] = []
    for regulator in glob_sorted("/sys/class/regulator/regulator*", root):
        rel = Path("/") / regulator.relative_to(root)
        name = read_text(rel / "name", root) or regulator.name
        if not name.lower().startswith(("vdd", "vcc", "dcdc", "ldo", "rk")):
            continue
        regulators.append(RegulatorInfo(
            name=name,
            state=read_text(rel / "state", root),
            microvolts=read_int(rel / "microvolts", root),
            microamps=read_int(rel / "microamps", root),
        ))
    return tuple(regulators[:16])
