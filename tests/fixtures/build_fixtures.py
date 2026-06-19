"""Build static fixture trees for integration tests.

Run this script once to populate tests/fixtures/ with realistic proc/sys trees.
The trees are checked into git so tests don't depend on this script at runtime.
"""

from pathlib import Path

FIXTURES = Path(__file__).parent


def write(root: Path, relative: str, value: str) -> None:
    path = root / relative.lstrip("/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def build_healthy_rk3562() -> None:
    root = FIXTURES / "healthy_rk3562"

    # Host
    write(root, "proc/device-tree/model", "Rockchip RK3562 Tablet\x00")
    write(root, "proc/device-tree/compatible", "rockchip,rk3562\x00vendor,samwise\x00")
    write(root, "proc/device-tree/serial-number", "RK3562-20240101\x00")
    write(root, "proc/uptime", "86400.50 172000.00")
    write(root, "proc/loadavg", "0.45 0.30 0.25 2/234 5678")

    # CPU (4 cores)
    write(root, "proc/stat",
        "cpu  10000 100 5000 80000 200 0 300 0 0 0\n"
        "cpu0 2500 25 1250 20000 50 0 75 0 0 0\n"
        "cpu1 2500 25 1250 20000 50 0 75 0 0 0\n"
        "cpu2 2500 25 1250 20000 50 0 75 0 0 0\n"
        "cpu3 2500 25 1250 20000 50 0 75 0 0 0\n"
    )
    for i in range(4):
        base = f"sys/devices/system/cpu/cpu{i}/cpufreq"
        write(root, f"{base}/scaling_cur_freq", "1800000")
        write(root, f"{base}/scaling_min_freq", "408000")
        write(root, f"{base}/scaling_max_freq", "2016000")

    # Memory
    write(root, "proc/meminfo",
        "MemTotal:        4096000 kB\n"
        "MemFree:          512000 kB\n"
        "MemAvailable:    2048000 kB\n"
        "Buffers:          128000 kB\n"
        "Cached:           768000 kB\n"
        "SReclaimable:      64000 kB\n"
        "SwapTotal:        512000 kB\n"
        "SwapFree:         480000 kB\n"
    )

    # Processes
    write(root, "proc/101/status",
        "Name:\trk-dashboard\nState:\tS (sleeping)\nVmRSS:\t  32768 kB\n")
    write(root, "proc/102/status",
        "Name:\tchromium\nState:\tS (sleeping)\nVmRSS:\t  262144 kB\n")
    write(root, "proc/103/status",
        "Name:\tkworker/0:1\nState:\tI (idle)\n")
    write(root, "proc/104/status",
        "Name:\tsshd\nState:\tS (sleeping)\nVmRSS:\t  8192 kB\n")

    # Mounts
    write(root, "proc/self/mountinfo",
        "22 1 179:1 / / rw,noatime shared:1 - ext4 /dev/mmcblk1p1 rw\n"
    )

    # Diskstats (SD=mmcblk1, eMMC=mmcblk0)
    write(root, "proc/diskstats",
        "179  0 mmcblk0 5000 0 200000 0 3000 0 100000 0 0 0 0 0\n"
        "179  1 mmcblk1 8000 0 300000 0 2000 0 80000 0 0 0 0 0\n"
    )

    # Block devices
    write(root, "sys/block/mmcblk0/device/type", "MMC")
    write(root, "sys/block/mmcblk0/size", "61071360")
    write(root, "sys/block/mmcblk0/removable", "0")
    write(root, "sys/block/mmcblk0/device/model", "HAG2e 32GB")
    write(root, "sys/block/mmcblk0/queue/rotational", "0")
    write(root, "sys/block/mmcblk1/device/type", "SD")
    write(root, "sys/block/mmcblk1/size", "124735488")
    write(root, "sys/block/mmcblk1/removable", "1")
    write(root, "sys/block/mmcblk1/device/model", "SD64G")
    write(root, "sys/block/mmcblk1/queue/rotational", "0")

    # Network
    write(root, "proc/net/dev",
        "Inter-|   Receive                                                |  Transmit\n"
        " face |bytes    packets errs drop fifo frame compressed multicast|bytes"
        "    packets errs drop fifo colls carrier compressed\n"
        "    lo: 1000 10 0 0 0 0 0 0 1000 10 0 0 0 0 0 0\n"
        " wlan0: 50000000 40000 0 0 0 0 0 0 5000000 30000 0 0 0 0 0 0\n"
    )
    write(root, "sys/class/net/lo/operstate", "unknown")
    write(root, "sys/class/net/wlan0/operstate", "up")

    # Thermal
    write(root, "sys/class/thermal/thermal_zone0/type", "soc-thermal")
    write(root, "sys/class/thermal/thermal_zone0/temp", "42500")
    write(root, "sys/class/thermal/thermal_zone1/type", "gpu-thermal")
    write(root, "sys/class/thermal/thermal_zone1/temp", "41000")

    # Power
    write(root, "sys/class/power_supply/battery/type", "Battery")
    write(root, "sys/class/power_supply/battery/status", "Discharging")
    write(root, "sys/class/power_supply/battery/voltage_now", "3850000")
    write(root, "sys/class/power_supply/battery/current_now", "-250000")
    write(root, "sys/class/power_supply/battery/capacity", "76")
    write(root, "sys/class/power_supply/usb/type", "USB")
    write(root, "sys/class/power_supply/usb/status", "Not charging")

    # NPU
    write(root, "sys/class/devfreq/ff300000.npu/load", "15@600000000Hz")
    write(root, "sys/class/devfreq/ff300000.npu/cur_freq", "600000000")
    write(root, "sys/class/devfreq/ff300000.npu/min_freq", "200000000")
    write(root, "sys/class/devfreq/ff300000.npu/max_freq", "1000000000")
    write(root, "sys/class/devfreq/ff300000.npu/governor", "rknpu_ondemand")
    write(root, "sys/module/rknpu/version", "0.9.8")

    # GPU devfreq
    write(root, "sys/class/devfreq/fde60000.gpu/cur_freq", "400000000")
    write(root, "sys/class/devfreq/fde60000.gpu/min_freq", "200000000")
    write(root, "sys/class/devfreq/fde60000.gpu/max_freq", "800000000")
    write(root, "sys/class/devfreq/fde60000.gpu/governor", "simple_ondemand")

    # Regulators
    write(root, "sys/class/regulator/regulator.1/name", "vdd_cpu")
    write(root, "sys/class/regulator/regulator.1/state", "enabled")
    write(root, "sys/class/regulator/regulator.1/microvolts", "900000")
    write(root, "sys/class/regulator/regulator.2/name", "vdd_gpu")
    write(root, "sys/class/regulator/regulator.2/state", "enabled")
    write(root, "sys/class/regulator/regulator.2/microvolts", "850000")


def build_partial_sysfs() -> None:
    root = FIXTURES / "partial_sysfs"
    write(root, "proc/stat", "cpu  100 0 100 800 0 0 0 0 0 0\ncpu0 100 0 100 800 0 0 0 0 0 0\n")
    write(root, "proc/meminfo", "MemTotal: 2048000 kB\nMemAvailable: 1024000 kB\n")
    write(root, "proc/uptime", "3600.0 7200.0")
    write(root, "proc/loadavg", "0.10 0.05 0.01 1/50 100")
    # No cpufreq, no devfreq, no thermal, no power, no network


def build_no_npu() -> None:
    root = FIXTURES / "no_npu"
    write(root, "proc/stat", "cpu  100 0 100 800 0 0 0 0 0 0\ncpu0 100 0 100 800 0 0 0 0 0 0\n")
    write(root, "proc/meminfo", "MemTotal: 2048000 kB\nMemAvailable: 1024000 kB\n")
    write(root, "proc/uptime", "3600.0 7200.0")
    write(root, "proc/loadavg", "0.10 0.05 0.01 1/50 100")
    write(root, "sys/class/thermal/thermal_zone0/type", "soc-thermal")
    write(root, "sys/class/thermal/thermal_zone0/temp", "38000")
    # No NPU devfreq, no rknpu module


def build_malformed_metrics() -> None:
    root = FIXTURES / "malformed_metrics"
    write(root, "proc/stat", "cpu  100 0 100 800 0 0 0 0 0 0\ncpu0 100 0 100 800 0 0 0 0 0 0\n")
    write(root, "proc/meminfo", "MemTotal: not_a_number kB\nMemAvailable: also_bad\n")
    write(root, "proc/uptime", "3600.0 7200.0")
    write(root, "proc/loadavg", "0.10 0.05 0.01 1/50 100")
    write(root, "sys/class/thermal/thermal_zone0/type", "soc-thermal")
    write(root, "sys/class/thermal/thermal_zone0/temp", "not_a_number")
    write(root, "sys/class/devfreq/ff300000.npu/load", "garbage_value")
    write(root, "sys/class/devfreq/ff300000.npu/cur_freq", "not_a_freq")


def build_battery_absent() -> None:
    root = FIXTURES / "battery_absent"
    write(root, "proc/stat", "cpu  100 0 100 800 0 0 0 0 0 0\ncpu0 100 0 100 800 0 0 0 0 0 0\n")
    write(root, "proc/meminfo", "MemTotal: 2048000 kB\nMemAvailable: 1024000 kB\n")
    write(root, "proc/uptime", "3600.0 7200.0")
    write(root, "proc/loadavg", "0.10 0.05 0.01 1/50 100")
    write(root, "sys/class/thermal/thermal_zone0/type", "soc-thermal")
    write(root, "sys/class/thermal/thermal_zone0/temp", "40000")
    # No power_supply directory at all


if __name__ == "__main__":
    build_healthy_rk3562()
    build_partial_sysfs()
    build_no_npu()
    build_malformed_metrics()
    build_battery_absent()
    print("Fixtures built successfully.")
