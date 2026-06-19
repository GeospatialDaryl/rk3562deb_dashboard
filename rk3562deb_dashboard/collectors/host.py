from __future__ import annotations

import platform
import socket
from pathlib import Path

from ..models import HostMetrics
from .base import ROOT, clean_dt_string, read_text


def collect_host(root: Path = ROOT) -> HostMetrics:
    model = read_text(Path("/proc/device-tree/model"), root)
    compatible = read_text(Path("/proc/device-tree/compatible"), root)
    serial = read_text(Path("/proc/device-tree/serial-number"), root)
    uptime_text = read_text(Path("/proc/uptime"), root) or "0 0"
    uptime_seconds = float(uptime_text.split()[0]) if uptime_text.split() else 0.0
    load_text = read_text(Path("/proc/loadavg"), root) or "0 0 0"
    load_values = [float(item) for item in load_text.split()[:3]]
    load = (
        load_values[0] if len(load_values) > 0 else 0.0,
        load_values[1] if len(load_values) > 1 else 0.0,
        load_values[2] if len(load_values) > 2 else 0.0,
    )
    return HostMetrics(
        hostname=socket.gethostname(),
        kernel=platform.release(),
        machine=platform.machine(),
        os=platform.platform(aliased=True, terse=True),
        model=clean_dt_string(model),
        compatible=clean_dt_string(compatible),
        serial=clean_dt_string(serial),
        uptime_seconds=round(uptime_seconds, 1),
        load=load,
    )
