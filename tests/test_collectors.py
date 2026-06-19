from __future__ import annotations

from pathlib import Path

from rk3562deb_dashboard.collectors import CollectorState, collect_snapshot
from rk3562deb_dashboard.collectors.cpu import CpuState, collect_cpu
from rk3562deb_dashboard.collectors.host import collect_host
from rk3562deb_dashboard.collectors.memory import collect_memory
from rk3562deb_dashboard.collectors.network import NetworkState, collect_network
from rk3562deb_dashboard.collectors.npu import collect_npu
from rk3562deb_dashboard.collectors.power import collect_power
from rk3562deb_dashboard.collectors.process import collect_processes
from rk3562deb_dashboard.collectors.rockchip import collect_rockchip
from rk3562deb_dashboard.collectors.storage import StorageState, collect_block_io, collect_disks
from rk3562deb_dashboard.collectors.thermal import collect_thermal
from rk3562deb_dashboard.models import MetricState


def write(root: Path, relative: str, value: str) -> None:
    path = root / relative.lstrip("/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def test_memory_uses_memavailable(tmp_path: Path) -> None:
    write(
        tmp_path,
        "/proc/meminfo",
        """
MemTotal:        1024 kB
MemFree:          128 kB
MemAvailable:     768 kB
Buffers:           16 kB
Cached:            32 kB
SReclaimable:       8 kB
SwapTotal:        512 kB
SwapFree:         256 kB
""".strip(),
    )

    mv = collect_memory(tmp_path)
    assert mv.is_available
    memory = mv.value
    assert memory is not None

    assert memory.total_bytes == 1024 * 1024
    assert memory.available_bytes == 768 * 1024
    assert memory.used_bytes == 256 * 1024
    assert memory.usage_percent == 25.0
    assert memory.cached_bytes == 40 * 1024


def test_cpu_usage_is_delta_based(tmp_path: Path) -> None:
    state = CpuState()
    write(
        tmp_path,
        "/proc/stat",
        "cpu  100 0 100 800 0 0 0 0 0 0\ncpu0 100 0 100 800 0 0 0 0 0 0\n",
    )
    first = collect_cpu(state, tmp_path)
    write(
        tmp_path,
        "/proc/stat",
        "cpu  150 0 150 900 0 0 0 0 0 0\ncpu0 150 0 150 900 0 0 0 0 0 0\n",
    )

    second = collect_cpu(state, tmp_path)

    assert first.value is not None
    assert first.value.usage_percent == 0.0
    assert second.value is not None
    assert second.value.usage_percent == 50.0
    assert second.value.cores[0].usage_percent == 50.0


def test_rockchip_collects_device_tree_devfreq_regulators_and_storage(tmp_path: Path) -> None:
    write(tmp_path, "/proc/device-tree/model", "RK3562 Test Board\x00")
    write(tmp_path, "/proc/device-tree/compatible", "rockchip,rk3562\x00vendor,board\x00")
    write(tmp_path, "/sys/class/devfreq/fde60000.gpu/cur_freq", "400000000")
    write(tmp_path, "/sys/class/devfreq/fde60000.gpu/governor", "simple_ondemand")
    write(tmp_path, "/sys/class/regulator/regulator.1/name", "vdd_cpu")
    write(tmp_path, "/sys/class/regulator/regulator.1/state", "enabled")
    write(tmp_path, "/sys/class/regulator/regulator.1/microvolts", "900000")
    write(tmp_path, "/sys/block/mmcblk0/size", "61071360")
    write(tmp_path, "/sys/block/mmcblk0/removable", "0")

    mv = collect_rockchip(tmp_path)
    assert mv.is_available
    rockchip = mv.value
    assert rockchip is not None

    assert rockchip.device_tree.model == "RK3562 Test Board"
    assert rockchip.device_tree.compatible is not None
    assert "rockchip,rk3562" in rockchip.device_tree.compatible
    assert rockchip.devfreq[0].frequency_hz == 400000000
    assert rockchip.regulators[0].microvolts == 900000
    assert rockchip.storage[0].name == "mmcblk0"
    assert rockchip.storage[0].size_bytes == 61071360 * 512


def test_host_parses_uptime_load_and_model(tmp_path: Path) -> None:
    write(tmp_path, "/proc/uptime", "12345.67 23456.78")
    write(tmp_path, "/proc/loadavg", "0.50 0.40 0.30 1/123 4567")
    write(tmp_path, "/proc/device-tree/model", "RK3562 Test Board\x00")

    host = collect_host(tmp_path)

    assert host.uptime_seconds == 12345.7
    assert host.load == (0.5, 0.4, 0.3)
    assert host.model == "RK3562 Test Board"


MOUNTINFO = (
    "26 1 179:25 / /mnt/internal rw,noatime shared:1 - ext4 /dev/mmcblk2p25 rw\n"
    "27 26 179:25 /home/frodo /home/frodo rw,noatime shared:2 - ext4 /dev/mmcblk2p25 rw\n"
)


def write_diskstats(root: Path, sectors_read: int, sectors_written: int) -> None:
    write(
        root,
        "/proc/diskstats",
        f"179 25 mmcblk2p25 100 0 {sectors_read} 0 50 0 {sectors_written} 0 0 0 0 0",
    )


def test_disks_rates_are_per_mount_for_shared_devices(tmp_path: Path) -> None:
    """Bind mounts share a device; each mount must still report the I/O delta."""

    state = StorageState()
    write(tmp_path, "/proc/self/mountinfo", MOUNTINFO)
    (tmp_path / "mnt/internal").mkdir(parents=True)
    (tmp_path / "home/frodo").mkdir(parents=True)
    write_diskstats(tmp_path, sectors_read=2048, sectors_written=1024)

    first = collect_disks(state, 1.0, tmp_path)
    write_diskstats(tmp_path, sectors_read=2248, sectors_written=1124)
    second = collect_disks(state, 1.0, tmp_path)

    assert first.is_available and first.value is not None
    assert second.is_available and second.value is not None
    assert [d.mount for d in first.value] == ["/mnt/internal", "/home/frodo"]
    assert all(d.read_bytes_per_sec == 0 for d in first.value)
    assert [d.read_bytes_per_sec for d in second.value] == [200 * 512, 200 * 512]
    assert [d.write_bytes_per_sec for d in second.value] == [100 * 512, 100 * 512]


def write_net_dev(root: Path, rx_bytes: int, tx_bytes: int) -> None:
    write(
        root,
        "/proc/net/dev",
        "Inter-|   Receive                                                |  Transmit\n"
        " face |bytes    packets errs drop fifo frame compressed multicast|bytes"
        "    packets errs drop fifo colls carrier compressed\n"
        f"  eth0: {rx_bytes} 10 0 0 0 0 0 0 {tx_bytes} 20 0 0 0 0 0 0\n",
    )


def test_network_rates_are_delta_based(tmp_path: Path) -> None:
    state = NetworkState()
    write_net_dev(tmp_path, rx_bytes=1000, tx_bytes=2000)
    write(tmp_path, "/sys/class/net/eth0/operstate", "up")

    first = collect_network(state, 1.0, tmp_path)
    write_net_dev(tmp_path, rx_bytes=3000, tx_bytes=2500)
    second = collect_network(state, 1.0, tmp_path)

    assert first.is_available and first.value is not None
    assert second.is_available and second.value is not None
    assert first.value[0].name == "eth0"
    assert first.value[0].operstate == "up"
    assert first.value[0].rx_bytes_per_sec == 0
    assert second.value[0].rx_bytes_per_sec == 2000
    assert second.value[0].tx_bytes_per_sec == 500


def test_thermal_reads_zones_in_celsius(tmp_path: Path) -> None:
    write(tmp_path, "/sys/class/thermal/thermal_zone0/type", "soc-thermal")
    write(tmp_path, "/sys/class/thermal/thermal_zone0/temp", "45500")
    write(tmp_path, "/sys/class/thermal/thermal_zone1/type", "gpu-thermal")

    mv = collect_thermal(tmp_path)
    assert mv.is_available and mv.value is not None
    zones = mv.value

    assert zones[0].name == "soc-thermal"
    assert zones[0].temperature_c == 45.5
    assert zones[1].name == "gpu-thermal"
    assert zones[1].temperature_c is None


def test_power_reads_battery_supply(tmp_path: Path) -> None:
    write(tmp_path, "/sys/class/power_supply/battery/type", "Battery")
    write(tmp_path, "/sys/class/power_supply/battery/status", "Discharging")
    write(tmp_path, "/sys/class/power_supply/battery/voltage_now", "3850000")
    write(tmp_path, "/sys/class/power_supply/battery/current_now", "-250000")
    write(tmp_path, "/sys/class/power_supply/battery/capacity", "76")

    mv = collect_power(tmp_path)
    assert mv.is_available and mv.value is not None
    supply = mv.value.supplies[0]

    assert supply.name == "battery"
    assert supply.status == "Discharging"
    assert supply.voltage_uv == 3850000
    assert supply.current_ua == -250000
    assert supply.capacity_percent == 76


def test_processes_counts_states_and_ranks_by_rss(tmp_path: Path) -> None:
    write(
        tmp_path,
        "/proc/101/status",
        "Name:\trk-dashboard\nState:\tS (sleeping)\nVmRSS:\t  20480 kB\n",
    )
    write(
        tmp_path,
        "/proc/102/status",
        "Name:\tbig-process\nState:\tR (running)\nVmRSS:\t  40960 kB\n",
    )
    write(tmp_path, "/proc/103/status", "Name:\tkthread\nState:\tS (sleeping)\n")

    mv = collect_processes(tmp_path)
    assert mv.is_available and mv.value is not None
    processes = mv.value

    assert processes.count == 3
    assert processes.states == {"S": 2, "R": 1}
    assert [p.pid for p in processes.top_memory] == [102, 101]
    assert processes.top_memory[0].rss_bytes == 40960 * 1024


def write_block_diskstats(root: Path, sd_written: int, emmc_written: int) -> None:
    write(
        root,
        "/proc/diskstats",
        f"179 0 mmcblk0 100 0 4096 0 50 0 {sd_written} 0 0 0 0 0\n"
        f"179 32 mmcblk2 100 0 8192 0 50 0 {emmc_written} 0 0 0 0 0\n",
    )


def test_block_io_reports_totals_and_kind_and_skips_boot_partitions(tmp_path: Path) -> None:
    state = StorageState()
    write(tmp_path, "/sys/block/mmcblk0/device/type", "SD")
    write(tmp_path, "/sys/block/mmcblk2/device/type", "MMC")
    (tmp_path / "sys/block/mmcblk2boot0").mkdir(parents=True)
    (tmp_path / "sys/block/mmcblk2rpmb").mkdir(parents=True)
    write_block_diskstats(tmp_path, sd_written=16, emmc_written=2048)

    first = collect_block_io(state, 1.0, tmp_path)
    write_block_diskstats(tmp_path, sd_written=16, emmc_written=2248)
    second = collect_block_io(state, 1.0, tmp_path)

    assert first.is_available and first.value is not None
    assert second.is_available and second.value is not None
    assert [d.name for d in first.value] == ["mmcblk0", "mmcblk2"]
    assert first.value[0].kind == "SD"
    assert first.value[1].kind == "MMC"
    assert first.value[0].written_bytes_total == 16 * 512
    assert first.value[1].written_bytes_total == 2048 * 512
    assert all(d.write_bytes_per_sec == 0 for d in first.value)
    assert second.value[0].write_bytes_per_sec == 0
    assert second.value[1].write_bytes_per_sec == 200 * 512


def test_npu_reads_devfreq_load_and_driver_version(tmp_path: Path) -> None:
    write(tmp_path, "/sys/class/devfreq/ff300000.npu/load", "42@1000000000Hz")
    write(tmp_path, "/sys/class/devfreq/ff300000.npu/cur_freq", "1000000000")
    write(tmp_path, "/sys/class/devfreq/ff300000.npu/max_freq", "1000000000")
    write(tmp_path, "/sys/class/devfreq/ff300000.npu/governor", "rknpu_ondemand")
    write(tmp_path, "/sys/class/devfreq/ff320000.gpu/load", "10@400000000Hz")
    write(tmp_path, "/sys/module/rknpu/version", "0.9.8")

    mv = collect_npu(tmp_path)
    assert mv.is_available and mv.value is not None
    npu = mv.value

    assert npu.driver_version == "0.9.8"
    assert [d.name for d in npu.devices] == ["ff300000.npu"]
    assert npu.devices[0].load_percent == 42
    assert npu.devices[0].frequency_hz == 1000000000
    assert npu.devices[0].governor == "rknpu_ondemand"


def test_npu_handles_missing_interfaces(tmp_path: Path) -> None:
    mv = collect_npu(tmp_path)
    assert mv.is_available and mv.value is not None
    assert mv.value.driver_version is None
    assert mv.value.devices == ()


def test_collect_snapshot_returns_typed_snapshot(tmp_path: Path) -> None:
    write(tmp_path, "/proc/stat", "cpu  100 0 100 800 0 0 0 0 0 0\n")
    write(tmp_path, "/proc/meminfo", "MemTotal: 1024 kB\nMemAvailable: 512 kB\n")
    state = CollectorState()
    snapshot = collect_snapshot(state, tmp_path)

    assert snapshot.host.hostname
    assert snapshot.cpu.state == MetricState.AVAILABLE
    assert snapshot.memory.state == MetricState.AVAILABLE
    assert snapshot.captured_at > 0
    assert snapshot.monotonic_seconds > 0
