"""Typed metric models for the RK3562 Debian dashboard.

These frozen dataclasses define the canonical data contract shared by the web
dashboard and the terminal UI.  Collectors produce MetricValue-wrapped domain
models; consumers never need to parse raw kernel files.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Generic, TypeVar

T = TypeVar("T")


class MetricState(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    PERMISSION_DENIED = "permission_denied"
    MALFORMED = "malformed"
    STALE = "stale"
    STATIC_OR_UNTRUSTED = "static_or_untrusted"


@dataclass(frozen=True, slots=True)
class MetricValue(Generic[T]):
    state: MetricState
    value: T | None = None
    detail: str | None = None
    source: str | None = None
    captured_at: datetime | None = None

    @staticmethod
    def available(value: T, source: str | None = None) -> MetricValue[T]:
        return MetricValue(state=MetricState.AVAILABLE, value=value, source=source)

    @staticmethod
    def unavailable(detail: str | None = None, source: str | None = None) -> MetricValue[T]:
        return MetricValue(state=MetricState.UNAVAILABLE, detail=detail, source=source)

    @staticmethod
    def unsupported(detail: str | None = None, source: str | None = None) -> MetricValue[T]:
        return MetricValue(state=MetricState.UNSUPPORTED, detail=detail, source=source)

    @staticmethod
    def permission_denied(
        detail: str | None = None, source: str | None = None
    ) -> MetricValue[T]:
        return MetricValue(state=MetricState.PERMISSION_DENIED, detail=detail, source=source)

    @staticmethod
    def malformed(detail: str | None = None, source: str | None = None) -> MetricValue[T]:
        return MetricValue(state=MetricState.MALFORMED, detail=detail, source=source)

    @staticmethod
    def stale(
        value: T, detail: str | None = None, source: str | None = None
    ) -> MetricValue[T]:
        return MetricValue(state=MetricState.STALE, value=value, detail=detail, source=source)

    @staticmethod
    def static_or_untrusted(
        value: T, detail: str | None = None, source: str | None = None
    ) -> MetricValue[T]:
        return MetricValue(
            state=MetricState.STATIC_OR_UNTRUSTED, value=value, detail=detail, source=source
        )

    @property
    def is_available(self) -> bool:
        return self.state == MetricState.AVAILABLE


# ---------------------------------------------------------------------------
# Host
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class HostMetrics:
    hostname: str
    kernel: str
    machine: str
    os: str
    model: str | None
    compatible: str | None
    serial: str | None
    uptime_seconds: float
    load: tuple[float, float, float]


# ---------------------------------------------------------------------------
# CPU
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CpuCoreMetrics:
    core_id: int
    usage_percent: float
    frequency_khz: int | None = None
    min_khz: int | None = None
    max_khz: int | None = None


@dataclass(frozen=True, slots=True)
class CpuMetrics:
    usage_percent: float
    cores: tuple[CpuCoreMetrics, ...]
    times: tuple[int, ...] = ()


# ---------------------------------------------------------------------------
# Memory / Swap
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class MemoryMetrics:
    total_bytes: int
    available_bytes: int
    used_bytes: int
    usage_percent: float
    buffers_bytes: int
    cached_bytes: int


@dataclass(frozen=True, slots=True)
class SwapMetrics:
    total_bytes: int
    used_bytes: int
    usage_percent: float


# ---------------------------------------------------------------------------
# Processes
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ProcessInfo:
    pid: int
    name: str
    state: str
    rss_bytes: int


@dataclass(frozen=True, slots=True)
class ProcessMetrics:
    count: int
    states: dict[str, int]
    top_memory: tuple[ProcessInfo, ...]


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class DiskMetrics:
    mount: str
    source: str
    filesystem: str
    total_bytes: int
    used_bytes: int
    usage_percent: float
    read_bytes_per_sec: int
    write_bytes_per_sec: int


@dataclass(frozen=True, slots=True)
class BlockIoDevice:
    name: str
    kind: str | None
    read_bytes_total: int
    written_bytes_total: int
    read_bytes_per_sec: int
    write_bytes_per_sec: int


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class NetworkInterfaceMetrics:
    name: str
    rx_bytes: int
    tx_bytes: int
    rx_bytes_per_sec: int
    tx_bytes_per_sec: int
    operstate: str | None


# ---------------------------------------------------------------------------
# Thermal
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ThermalZoneMetrics:
    name: str
    temperature_c: float | None
    path: str


# ---------------------------------------------------------------------------
# Power
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class PowerSupply:
    name: str
    type: str | None
    status: str | None
    voltage_uv: int | None
    current_ua: int | None
    capacity_percent: int | None


@dataclass(frozen=True, slots=True)
class PowerMetrics:
    supplies: tuple[PowerSupply, ...]


# ---------------------------------------------------------------------------
# NPU
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class NpuDevice:
    name: str
    load_percent: int | None
    frequency_hz: int | None
    min_hz: int | None
    max_hz: int | None
    governor: str | None


@dataclass(frozen=True, slots=True)
class NpuMetrics:
    driver_version: str | None
    devices: tuple[NpuDevice, ...]


# ---------------------------------------------------------------------------
# Rockchip
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class DeviceTreeInfo:
    model: str | None
    compatible: str | None


@dataclass(frozen=True, slots=True)
class DevfreqDevice:
    name: str
    frequency_hz: int | None
    min_hz: int | None
    max_hz: int | None
    governor: str | None
    path: str


@dataclass(frozen=True, slots=True)
class RegulatorInfo:
    name: str
    state: str | None
    microvolts: int | None
    microamps: int | None


@dataclass(frozen=True, slots=True)
class StorageIdentity:
    name: str
    model: str | None
    type: str | None
    size_bytes: int
    removable: int | None


@dataclass(frozen=True, slots=True)
class RockchipMetrics:
    device_tree: DeviceTreeInfo
    devfreq: tuple[DevfreqDevice, ...]
    regulators: tuple[RegulatorInfo, ...]
    storage: tuple[StorageIdentity, ...]


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class HistoryPoint:
    monotonic_seconds: float
    wall_time: float
    cpu_percent: float | None
    memory_percent: float | None
    max_temperature_c: float | None
    sd_write_bytes_per_sec: int | None
    emmc_write_bytes_per_sec: int | None


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    captured_at: float
    monotonic_seconds: float
    host: HostMetrics
    cpu: MetricValue[CpuMetrics]
    memory: MetricValue[MemoryMetrics]
    swap: MetricValue[SwapMetrics]
    processes: MetricValue[ProcessMetrics]
    disks: MetricValue[tuple[DiskMetrics, ...]]
    block_io: MetricValue[tuple[BlockIoDevice, ...]]
    network: MetricValue[tuple[NetworkInterfaceMetrics, ...]]
    thermal: MetricValue[tuple[ThermalZoneMetrics, ...]]
    power: MetricValue[PowerMetrics]
    npu: MetricValue[NpuMetrics]
    rockchip: MetricValue[RockchipMetrics]
