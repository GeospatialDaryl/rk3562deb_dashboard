"""System metrics collectors for the RK3562 Debian dashboard.

The collectors intentionally avoid third-party dependencies so the dashboard can
run on a freshly installed embedded Debian image. All reads are best-effort:
missing kernel interfaces produce empty fields instead of hard failures.
"""

from __future__ import annotations

import os
import platform
import re
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path("/")


@dataclass(slots=True)
class CollectorState:
    """Previous snapshots required to calculate rates between samples."""

    cpu: dict[str, list[int]] = field(default_factory=dict)
    disks: dict[str, tuple[int, int]] = field(default_factory=dict)
    net: dict[str, tuple[int, int]] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.monotonic)


def _read_text(path: Path, root: Path = ROOT) -> str | None:
    try:
        return (root / path.relative_to("/")).read_text(encoding="utf-8", errors="replace").strip()
    except (FileNotFoundError, PermissionError, OSError):
        return None


def _read_int(path: Path, root: Path = ROOT) -> int | None:
    text = _read_text(path, root)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _glob(path: str, root: Path = ROOT) -> list[Path]:
    return sorted(root.glob(path.lstrip("/")))


def _relative_sys_path(path: Path, root: Path = ROOT) -> str:
    try:
        return "/" + str(path.relative_to(root))
    except ValueError:
        return str(path)


def _percent(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round(max(0.0, min(100.0, (numerator / denominator) * 100.0)), 1)


def collect_snapshot(state: CollectorState | None = None, root: Path = ROOT) -> dict[str, Any]:
    """Collect a complete dashboard snapshot.

    Args:
        state: Optional mutable state used to compute deltas for CPU, disk, and network rates.
        root: Alternate filesystem root, primarily for tests.
    """

    state = state or CollectorState()
    now = time.monotonic()
    interval = max(0.001, now - state.timestamp)
    snapshot = {
        "timestamp": time.time(),
        "host": collect_host(root),
        "cpu": collect_cpu(state, root),
        "memory": collect_memory(root),
        "swap": collect_swap(root),
        "processes": collect_processes(root),
        "disks": collect_disks(state, interval, root),
        "network": collect_network(state, interval, root),
        "thermal": collect_thermal(root),
        "power": collect_power(root),
        "rockchip": collect_rockchip(root),
    }
    state.timestamp = now
    return snapshot


def collect_host(root: Path = ROOT) -> dict[str, Any]:
    model = _read_text(Path("/proc/device-tree/model"), root)
    compatible = _read_text(Path("/proc/device-tree/compatible"), root)
    serial = _read_text(Path("/proc/device-tree/serial-number"), root)
    uptime_text = _read_text(Path("/proc/uptime"), root) or "0 0"
    uptime_seconds = float(uptime_text.split()[0]) if uptime_text.split() else 0.0
    load_text = _read_text(Path("/proc/loadavg"), root) or "0 0 0"
    load = [float(item) for item in load_text.split()[:3]]
    return {
        "hostname": socket.gethostname(),
        "kernel": platform.release(),
        "machine": platform.machine(),
        "os": platform.platform(aliased=True, terse=True),
        "model": _clean_dt_string(model),
        "compatible": _clean_dt_string(compatible),
        "serial": _clean_dt_string(serial),
        "uptime_seconds": round(uptime_seconds, 1),
        "load": load,
    }


def _clean_dt_string(value: str | None) -> str | None:
    if not value:
        return None
    return value.replace("\x00", ", ").strip(" ,")


def collect_cpu(state: CollectorState, root: Path = ROOT) -> dict[str, Any]:
    stat = _read_text(Path("/proc/stat"), root) or ""
    cores: list[dict[str, Any]] = []
    aggregate: dict[str, Any] | None = None
    current: dict[str, list[int]] = {}

    for line in stat.splitlines():
        if not line.startswith("cpu"):
            continue
        name, *values_text = line.split()
        if not values_text or not name.replace("cpu", "", 1).isdigit() and name != "cpu":
            continue
        values = [int(value) for value in values_text[:10]]
        current[name] = values
        previous = state.cpu.get(name)
        usage = _cpu_usage(previous, values)
        entry = {"name": name, "usage_percent": usage, "times": values}
        if name == "cpu":
            aggregate = entry
        else:
            core_id = int(name[3:])
            entry.update(collect_cpu_frequency(core_id, root))
            cores.append(entry)

    state.cpu = current
    return {"total": aggregate or {"name": "cpu", "usage_percent": 0.0}, "cores": cores}


def _cpu_usage(previous: list[int] | None, current: list[int]) -> float:
    if previous is None:
        return 0.0
    total_delta = sum(current) - sum(previous)
    idle_delta = (current[3] + current[4]) - (previous[3] + previous[4])
    return _percent(total_delta - idle_delta, total_delta)


def collect_cpu_frequency(core_id: int, root: Path = ROOT) -> dict[str, int | None]:
    base = Path(f"/sys/devices/system/cpu/cpu{core_id}/cpufreq")
    return {
        "frequency_khz": _read_int(base / "scaling_cur_freq", root),
        "min_khz": _read_int(base / "scaling_min_freq", root),
        "max_khz": _read_int(base / "scaling_max_freq", root),
    }


def _parse_meminfo(root: Path = ROOT) -> dict[str, int]:
    meminfo = _read_text(Path("/proc/meminfo"), root) or ""
    parsed: dict[str, int] = {}
    for line in meminfo.splitlines():
        match = re.match(r"^(\w+):\s+(\d+)", line)
        if match:
            parsed[match.group(1)] = int(match.group(2)) * 1024
    return parsed


def collect_memory(root: Path = ROOT) -> dict[str, Any]:
    mem = _parse_meminfo(root)
    total = mem.get("MemTotal", 0)
    available = mem.get("MemAvailable", 0)
    used = max(0, total - available)
    return {
        "total_bytes": total,
        "available_bytes": available,
        "used_bytes": used,
        "usage_percent": _percent(used, total),
        "buffers_bytes": mem.get("Buffers", 0),
        "cached_bytes": mem.get("Cached", 0) + mem.get("SReclaimable", 0),
    }


def collect_swap(root: Path = ROOT) -> dict[str, Any]:
    mem = _parse_meminfo(root)
    total = mem.get("SwapTotal", 0)
    free = mem.get("SwapFree", 0)
    used = max(0, total - free)
    return {"total_bytes": total, "used_bytes": used, "usage_percent": _percent(used, total)}


def collect_processes(root: Path = ROOT) -> dict[str, Any]:
    proc_root = root / "proc"
    process_dirs = (
        [path for path in proc_root.iterdir() if path.name.isdigit()]
        if proc_root.exists()
        else []
    )
    states: dict[str, int] = {}
    top_memory: list[dict[str, Any]] = []

    for proc in process_dirs:
        status = _read_text(Path("/proc") / proc.name / "status", root) or ""
        fields = _parse_status(status)
        state = fields.get("State", "?")[:1]
        states[state] = states.get(state, 0) + 1
        rss_kb = _status_kb(fields.get("VmRSS"))
        if rss_kb > 0:
            top_memory.append(
                {
                    "pid": int(proc.name),
                    "name": fields.get("Name", proc.name),
                    "state": state,
                    "rss_bytes": rss_kb * 1024,
                }
            )

    top_memory.sort(key=lambda item: item["rss_bytes"], reverse=True)
    return {"count": len(process_dirs), "states": states, "top_memory": top_memory[:8]}


def _parse_status(status: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in status.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            parsed[key] = value.strip()
    return parsed


def _status_kb(value: str | None) -> int:
    if not value:
        return 0
    match = re.match(r"^(\d+)", value)
    return int(match.group(1)) if match else 0


def collect_disks(
    state: CollectorState, interval: float, root: Path = ROOT
) -> list[dict[str, Any]]:
    mounts = _read_text(Path("/proc/self/mountinfo"), root) or ""
    diskstats = _parse_diskstats(root)
    devices_seen: set[str] = set()
    disks: list[dict[str, Any]] = []

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
        # Key deltas by mount point, not device: bind mounts share a device, and a
        # device-keyed store would let the first mount consume the whole delta.
        previous_reads, previous_writes = state.disks.get(mount_point, (reads, writes))
        state.disks[mount_point] = (reads, writes)
        disks.append(
            {
                "mount": mount_point,
                "source": source,
                "filesystem": fs_type,
                **usage,
                "read_bytes_per_sec": max(0, round((reads - previous_reads) / interval)),
                "write_bytes_per_sec": max(0, round((writes - previous_writes) / interval)),
            }
        )
    return disks


def _disk_usage(mount_point: str, root: Path = ROOT) -> dict[str, Any]:
    path = root / mount_point.lstrip("/")
    try:
        usage = os.statvfs(path)
    except OSError:
        return {"total_bytes": 0, "used_bytes": 0, "usage_percent": 0.0}
    total = usage.f_blocks * usage.f_frsize
    free = usage.f_bavail * usage.f_frsize
    used = max(0, total - free)
    return {"total_bytes": total, "used_bytes": used, "usage_percent": _percent(used, total)}


def _parse_diskstats(root: Path = ROOT) -> dict[str, tuple[int, int]]:
    text = _read_text(Path("/proc/diskstats"), root) or ""
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


def collect_network(
    state: CollectorState, interval: float, root: Path = ROOT
) -> list[dict[str, Any]]:
    text = _read_text(Path("/proc/net/dev"), root) or ""
    interfaces: list[dict[str, Any]] = []
    for line in text.splitlines()[2:]:
        if ":" not in line:
            continue
        name, data = line.split(":", 1)
        name = name.strip()
        fields = data.split()
        rx_bytes = int(fields[0])
        tx_bytes = int(fields[8])
        previous_rx, previous_tx = state.net.get(name, (rx_bytes, tx_bytes))
        state.net[name] = (rx_bytes, tx_bytes)
        interfaces.append(
            {
                "name": name,
                "rx_bytes": rx_bytes,
                "tx_bytes": tx_bytes,
                "rx_bytes_per_sec": max(0, round((rx_bytes - previous_rx) / interval)),
                "tx_bytes_per_sec": max(0, round((tx_bytes - previous_tx) / interval)),
                "operstate": _read_text(Path(f"/sys/class/net/{name}/operstate"), root),
            }
        )
    return interfaces


def collect_thermal(root: Path = ROOT) -> list[dict[str, Any]]:
    zones: list[dict[str, Any]] = []
    for zone in _glob("/sys/class/thermal/thermal_zone*", root):
        temp_milli = _read_int(Path("/") / zone.relative_to(root) / "temp", root)
        zones.append(
            {
                "name": _read_text(Path("/") / zone.relative_to(root) / "type", root) or zone.name,
                "temperature_c": round(temp_milli / 1000.0, 1) if temp_milli is not None else None,
                "path": _relative_sys_path(zone, root),
            }
        )
    return zones


def collect_power(root: Path = ROOT) -> dict[str, Any]:
    supplies: list[dict[str, Any]] = []
    for supply in _glob("/sys/class/power_supply/*", root):
        supplies.append(
            {
                "name": supply.name,
                "type": _read_text(Path("/") / supply.relative_to(root) / "type", root),
                "status": _read_text(Path("/") / supply.relative_to(root) / "status", root),
                "voltage_uv": _read_int(Path("/") / supply.relative_to(root) / "voltage_now", root),
                "current_ua": _read_int(Path("/") / supply.relative_to(root) / "current_now", root),
                "capacity_percent": _read_int(
                    Path("/") / supply.relative_to(root) / "capacity", root
                ),
            }
        )
    return {"supplies": supplies}


def collect_rockchip(root: Path = ROOT) -> dict[str, Any]:
    """Collect Rockchip/RK3562-specific details exposed by common Debian kernels."""

    return {
        "device_tree": {
            "model": _clean_dt_string(_read_text(Path("/proc/device-tree/model"), root)),
            "compatible": _clean_dt_string(_read_text(Path("/proc/device-tree/compatible"), root)),
        },
        "devfreq": collect_devfreq(root),
        "regulators": collect_regulators(root),
        "storage": collect_storage_identity(root),
    }


def collect_devfreq(root: Path = ROOT) -> list[dict[str, Any]]:
    devices: list[dict[str, Any]] = []
    for devfreq in _glob("/sys/class/devfreq/*", root):
        rel = Path("/") / devfreq.relative_to(root)
        devices.append(
            {
                "name": devfreq.name,
                "frequency_hz": _read_int(rel / "cur_freq", root),
                "min_hz": _read_int(rel / "min_freq", root),
                "max_hz": _read_int(rel / "max_freq", root),
                "governor": _read_text(rel / "governor", root),
                "path": _relative_sys_path(devfreq, root),
            }
        )
    return devices


def collect_regulators(root: Path = ROOT) -> list[dict[str, Any]]:
    regulators: list[dict[str, Any]] = []
    for regulator in _glob("/sys/class/regulator/regulator*", root):
        rel = Path("/") / regulator.relative_to(root)
        name = _read_text(rel / "name", root) or regulator.name
        if not name.lower().startswith(("vdd", "vcc", "dcdc", "ldo", "rk")):
            continue
        regulators.append(
            {
                "name": name,
                "state": _read_text(rel / "state", root),
                "microvolts": _read_int(rel / "microvolts", root),
                "microamps": _read_int(rel / "microamps", root),
            }
        )
    return regulators[:16]


def collect_storage_identity(root: Path = ROOT) -> list[dict[str, Any]]:
    devices: list[dict[str, Any]] = []
    for block in _glob("/sys/block/*", root):
        if not block.name.startswith(("mmcblk", "nvme", "sd")):
            continue
        rel = Path("/") / block.relative_to(root)
        devices.append(
            {
                "name": block.name,
                "model": _read_text(rel / "device/model", root),
                "type": _read_text(rel / "queue/rotational", root),
                "size_bytes": (_read_int(rel / "size", root) or 0) * 512,
                "removable": _read_int(rel / "removable", root),
            }
        )
    return devices
