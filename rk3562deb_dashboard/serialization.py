"""Convert typed models to JSON-serializable dicts for the web API.

This keeps the HTTP layer compatible with the existing browser dashboard
while the internal data layer uses typed models.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from .models import (
    BlockIoDevice,
    CpuMetrics,
    DashboardSnapshot,
    DiskMetrics,
    HistoryPoint,
    HostMetrics,
    MemoryMetrics,
    MetricValue,
    NetworkInterfaceMetrics,
    NpuMetrics,
    PowerMetrics,
    ProcessMetrics,
    RockchipMetrics,
    SwapMetrics,
    ThermalZoneMetrics,
)


def _unwrap(mv: MetricValue[Any]) -> Any:
    return mv.value


def snapshot_to_dict(snapshot: DashboardSnapshot) -> dict[str, Any]:
    return {
        "timestamp": snapshot.captured_at,
        "host": _host_to_dict(snapshot.host),
        "cpu": _cpu_to_dict(snapshot.cpu),
        "memory": _memory_to_dict(snapshot.memory),
        "swap": _swap_to_dict(snapshot.swap),
        "processes": _processes_to_dict(snapshot.processes),
        "disks": _disks_to_dict(snapshot.disks),
        "block_io": _block_io_to_dict(snapshot.block_io),
        "network": _network_to_dict(snapshot.network),
        "thermal": _thermal_to_dict(snapshot.thermal),
        "power": _power_to_dict(snapshot.power),
        "npu": _npu_to_dict(snapshot.npu),
        "rockchip": _rockchip_to_dict(snapshot.rockchip),
    }


def _host_to_dict(host: HostMetrics) -> dict[str, Any]:
    return {
        "hostname": host.hostname,
        "kernel": host.kernel,
        "machine": host.machine,
        "os": host.os,
        "model": host.model,
        "compatible": host.compatible,
        "serial": host.serial,
        "uptime_seconds": host.uptime_seconds,
        "load": list(host.load),
    }


def _cpu_to_dict(mv: MetricValue[CpuMetrics]) -> dict[str, Any]:
    cpu = _unwrap(mv)
    if cpu is None:
        return {"total": {"name": "cpu", "usage_percent": 0.0}, "cores": []}
    cores = []
    for c in cpu.cores:
        entry: dict[str, Any] = {
            "name": f"cpu{c.core_id}",
            "usage_percent": c.usage_percent,
            "times": [],
            "frequency_khz": c.frequency_khz,
            "min_khz": c.min_khz,
            "max_khz": c.max_khz,
        }
        cores.append(entry)
    return {
        "total": {"name": "cpu", "usage_percent": cpu.usage_percent, "times": list(cpu.times)},
        "cores": cores,
    }


def _memory_to_dict(mv: MetricValue[MemoryMetrics]) -> dict[str, Any]:
    mem = _unwrap(mv)
    if mem is None:
        return {
            "total_bytes": 0, "available_bytes": 0, "used_bytes": 0,
            "usage_percent": 0.0, "buffers_bytes": 0, "cached_bytes": 0,
        }
    return dataclasses.asdict(mem)


def _swap_to_dict(mv: MetricValue[SwapMetrics]) -> dict[str, Any]:
    swap = _unwrap(mv)
    if swap is None:
        return {"total_bytes": 0, "used_bytes": 0, "usage_percent": 0.0}
    return dataclasses.asdict(swap)


def _processes_to_dict(mv: MetricValue[ProcessMetrics]) -> dict[str, Any]:
    procs = _unwrap(mv)
    if procs is None:
        return {"count": 0, "states": {}, "top_memory": []}
    return {
        "count": procs.count,
        "states": procs.states,
        "top_memory": [dataclasses.asdict(p) for p in procs.top_memory],
    }


def _disks_to_dict(mv: MetricValue[tuple[DiskMetrics, ...]]) -> list[dict[str, Any]]:
    disks = _unwrap(mv)
    if disks is None:
        return []
    return [dataclasses.asdict(d) for d in disks]


def _block_io_to_dict(mv: MetricValue[tuple[BlockIoDevice, ...]]) -> list[dict[str, Any]]:
    devices = _unwrap(mv)
    if devices is None:
        return []
    return [dataclasses.asdict(d) for d in devices]


def _network_to_dict(
    mv: MetricValue[tuple[NetworkInterfaceMetrics, ...]],
) -> list[dict[str, Any]]:
    interfaces = _unwrap(mv)
    if interfaces is None:
        return []
    return [dataclasses.asdict(i) for i in interfaces]


def _thermal_to_dict(
    mv: MetricValue[tuple[ThermalZoneMetrics, ...]],
) -> list[dict[str, Any]]:
    zones = _unwrap(mv)
    if zones is None:
        return []
    return [dataclasses.asdict(z) for z in zones]


def _power_to_dict(mv: MetricValue[PowerMetrics]) -> dict[str, Any]:
    power = _unwrap(mv)
    if power is None:
        return {"supplies": []}
    return {"supplies": [dataclasses.asdict(s) for s in power.supplies]}


def _npu_to_dict(mv: MetricValue[NpuMetrics]) -> dict[str, Any]:
    npu = _unwrap(mv)
    if npu is None:
        return {"driver_version": None, "devices": []}
    return {
        "driver_version": npu.driver_version,
        "devices": [dataclasses.asdict(d) for d in npu.devices],
    }


def _rockchip_to_dict(mv: MetricValue[RockchipMetrics]) -> dict[str, Any]:
    rk = _unwrap(mv)
    if rk is None:
        return {"device_tree": {}, "devfreq": [], "regulators": [], "storage": []}
    return {
        "device_tree": dataclasses.asdict(rk.device_tree),
        "devfreq": [dataclasses.asdict(d) for d in rk.devfreq],
        "regulators": [dataclasses.asdict(r) for r in rk.regulators],
        "storage": [dataclasses.asdict(s) for s in rk.storage],
    }


def history_point_to_dict(point: HistoryPoint) -> dict[str, Any]:
    return {
        "t": point.wall_time,
        "cpu": point.cpu_percent,
        "mem": point.memory_percent,
        "temp": point.max_temperature_c,
        "sd_write": point.sd_write_bytes_per_sec,
        "emmc_write": point.emmc_write_bytes_per_sec,
    }
