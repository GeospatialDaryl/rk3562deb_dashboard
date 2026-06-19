from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..models import MetricValue, NetworkInterfaceMetrics
from .base import ROOT, read_text


@dataclass(slots=True)
class NetworkState:
    previous: dict[str, tuple[int, int]] = field(default_factory=dict)


def collect_network(
    state: NetworkState, interval: float, root: Path = ROOT
) -> MetricValue[tuple[NetworkInterfaceMetrics, ...]]:
    text = read_text(Path("/proc/net/dev"), root) or ""
    interfaces: list[NetworkInterfaceMetrics] = []
    for line in text.splitlines()[2:]:
        if ":" not in line:
            continue
        name, data = line.split(":", 1)
        name = name.strip()
        fields = data.split()
        rx_bytes = int(fields[0])
        tx_bytes = int(fields[8])
        previous_rx, previous_tx = state.previous.get(name, (rx_bytes, tx_bytes))
        state.previous[name] = (rx_bytes, tx_bytes)
        interfaces.append(NetworkInterfaceMetrics(
            name=name,
            rx_bytes=rx_bytes,
            tx_bytes=tx_bytes,
            rx_bytes_per_sec=max(0, round((rx_bytes - previous_rx) / interval)),
            tx_bytes_per_sec=max(0, round((tx_bytes - previous_tx) / interval)),
            operstate=read_text(Path(f"/sys/class/net/{name}/operstate"), root),
        ))
    return MetricValue.available(tuple(interfaces))
