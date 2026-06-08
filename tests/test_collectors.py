from __future__ import annotations

from pathlib import Path

from rk3562deb_dashboard.collectors import (
    CollectorState,
    collect_cpu,
    collect_memory,
    collect_rockchip,
)


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

    memory = collect_memory(tmp_path)

    assert memory["total_bytes"] == 1024 * 1024
    assert memory["available_bytes"] == 768 * 1024
    assert memory["used_bytes"] == 256 * 1024
    assert memory["usage_percent"] == 25.0
    assert memory["cached_bytes"] == 40 * 1024


def test_cpu_usage_is_delta_based(tmp_path: Path) -> None:
    state = CollectorState()
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

    assert first["total"]["usage_percent"] == 0.0
    assert second["total"]["usage_percent"] == 50.0
    assert second["cores"][0]["usage_percent"] == 50.0


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

    rockchip = collect_rockchip(tmp_path)

    assert rockchip["device_tree"]["model"] == "RK3562 Test Board"
    assert "rockchip,rk3562" in rockchip["device_tree"]["compatible"]
    assert rockchip["devfreq"][0]["frequency_hz"] == 400000000
    assert rockchip["regulators"][0]["microvolts"] == 900000
    assert rockchip["storage"][0]["name"] == "mmcblk0"
    assert rockchip["storage"][0]["size_bytes"] == 61071360 * 512
