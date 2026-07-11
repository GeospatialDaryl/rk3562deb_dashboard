"""RKDashboardTui application shell over TuiMonsterApp."""

from __future__ import annotations

import curses
import time
from datetime import UTC, datetime

from pyTuiMonster import TuiConfig, TuiMonsterApp, key_binding

from ..models import DashboardSnapshot, HistoryPoint, MetricState
from ..sampler import DashboardSampler
from .formatting import (
    bar_gauge,
    format_bytes,
    format_frequency_mhz,
    format_percent,
    format_rate,
    format_temperature,
    format_uptime,
)
from .layout import LayoutMode, compute_layout
from .screens.process import SORT_CYCLE, draw_process_screen
from .state import SCREEN_NAMES, ScreenId, TuiState
from .widgets.sparkline import render_sparkline

HELP_TEXT = [
    "RK3562 Dashboard TUI — Keyboard Help",
    "",
    "  q / Q / Ctrl-C   Exit",
    "  ? / h            Toggle this help",
    "  Esc              Close overlay / return to overview",
    "  1-7              Switch screen directly",
    "  Tab              Next screen",
    "  Shift-Tab        Previous screen",
    "  p                Pause / resume refresh",
    "  r                Immediate refresh",
    "  d                Toggle detail info",
    "  c                Toggle compact mode",
    "  s                Cycle process sort (CPU/MEM/PID/Name)",
    "",
    "  Screens: 1=Overview  2=CPU  3=Storage  4=Network",
    "           5=Thermal/Power  6=NPU/Rockchip  7=Processes",
]


class RKDashboardTui(TuiMonsterApp):
    def __init__(
        self,
        sampler: DashboardSampler,
        interval: float = 2.0,
        once: bool = False,
        no_color: bool = False,
        ascii_only: bool = False,
    ) -> None:
        config = TuiConfig(
            refresh_rate=1 / 30,
            stop_keys=(ord("q"), ord("Q")),
        )
        super().__init__(config)
        self._sampler = sampler
        self._state = TuiState()
        self._snapshot: DashboardSnapshot | None = None
        self._history: list[HistoryPoint] = []
        self._collection_interval = interval
        self._last_collection = 0.0
        self._once = once
        self._no_color = no_color
        self._ascii_only = ascii_only
        self._force_compact = False
        self._colors_initialized = False

    # -- Key bindings --

    @key_binding(ord("?"), ord("h"))
    def _toggle_help(self, _key: int) -> None:
        self._state.show_help = not self._state.show_help

    @key_binding(ord("p"))
    def _toggle_pause(self, _key: int) -> None:
        self._state.is_paused = not self._state.is_paused

    @key_binding(ord("r"))
    def _force_refresh(self, _key: int) -> None:
        now = time.monotonic()
        if now - self._last_collection >= 0.25:
            self._snapshot = self._sampler.sample_now()
            self._history = self._sampler.history()
            self._last_collection = now

    @key_binding(ord("d"))
    def _toggle_detail(self, _key: int) -> None:
        self._state.show_detail = not self._state.show_detail

    @key_binding(ord("c"))
    def _toggle_compact(self, _key: int) -> None:
        self._force_compact = not self._force_compact

    @key_binding(ord("s"))
    def _cycle_process_sort(self, _key: int) -> None:
        cur = self._state.selected_process_sort
        idx = SORT_CYCLE.index(cur) if cur in SORT_CYCLE else -1
        self._state.selected_process_sort = SORT_CYCLE[(idx + 1) % len(SORT_CYCLE)]

    @key_binding(ord("\t"))
    def _next_screen(self, _key: int) -> None:
        self._state.next_screen()

    @key_binding(curses.KEY_BTAB)
    def _prev_screen(self, _key: int) -> None:
        self._state.prev_screen()

    @key_binding(27)  # Escape
    def _on_escape(self, _key: int) -> None:
        if self._state.show_help:
            self._state.show_help = False
        else:
            self._state.active_screen = ScreenId.OVERVIEW

    @key_binding(
        ord("1"), ord("2"), ord("3"), ord("4"),
        ord("5"), ord("6"), ord("7"),
    )
    def _switch_screen(self, key: int) -> None:
        self._state.go_to_screen(key - ord("0"))

    # -- Lifecycle --

    def on_start(self) -> None:
        self._init_colors()
        self._snapshot = self._sampler.sample_now()
        self._history = self._sampler.history()
        self._last_collection = time.monotonic()

    def update(self) -> None:
        if self._state.is_paused:
            return
        now = time.monotonic()
        if now - self._last_collection >= self._collection_interval:
            self._snapshot = self._sampler.sample_now()
            self._history = self._sampler.history()
            self._last_collection = now

    def draw(self) -> None:
        if self._stdscr is None:
            return
        self.clear()
        height, width = self._stdscr.getmaxyx()
        self._state.last_size = (height, width)
        layout = compute_layout(height, width)

        if layout.mode == LayoutMode.TOO_SMALL:
            self._draw_too_small(height, width)
        elif self._state.show_help:
            self._draw_help(height, width)
        elif self._state.active_screen == ScreenId.PROCESSES:
            draw_process_screen(self, 0, width, height)
        else:
            effective_mode = layout.mode
            if self._force_compact and effective_mode != LayoutMode.COMPACT:
                effective_mode = LayoutMode.COMPACT
            self._draw_overview(height, width, effective_mode)

        self._draw_status_line(height, width)
        self.refresh()

        if self._once:
            self.stop()

    # -- Color initialization --

    def _init_colors(self) -> None:
        if self._no_color:
            return
        try:
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)
            curses.init_pair(2, curses.COLOR_YELLOW, -1)
            curses.init_pair(3, curses.COLOR_RED, -1)
            curses.init_pair(4, curses.COLOR_CYAN, -1)
            curses.init_pair(5, curses.COLOR_MAGENTA, -1)
            curses.init_pair(6, curses.COLOR_WHITE, -1)
            self._colors_initialized = True
        except curses.error:
            pass

    def _color(self, pair: int) -> int:
        if not self._colors_initialized:
            return 0
        return curses.color_pair(pair)

    def _attr_label(self) -> int:
        return self._color(4) | curses.A_BOLD

    def _attr_value(self) -> int:
        return 0

    def _attr_header(self) -> int:
        return self._color(4) | curses.A_BOLD

    def _attr_warn(self) -> int:
        return self._color(2)

    def _attr_critical(self) -> int:
        return self._color(3) | curses.A_BOLD

    def _attr_unavailable(self) -> int:
        return self._color(5)

    def _attr_good(self) -> int:
        return self._color(1)

    def _severity_attr(self, percent: float) -> int:
        if percent >= 90:
            return self._attr_critical()
        if percent >= 70:
            return self._attr_warn()
        return self._attr_good()

    def _temp_attr(self, celsius: float | None) -> int:
        if celsius is None:
            return self._attr_value()
        if celsius >= 80:
            return self._attr_critical()
        if celsius >= 60:
            return self._attr_warn()
        return self._attr_value()

    # -- Helpers --

    def _make_bar(self, percent: float, width: int) -> str:
        if self._ascii_only:
            return bar_gauge(percent, width, "#", "-")
        return bar_gauge(percent, width)

    def _sparkline(self, values: list[float | None], width: int) -> str:
        return render_sparkline(
            values, width, ascii_only=self._ascii_only,
        )

    def _state_label(self, state: MetricState) -> str:
        labels = {
            MetricState.UNAVAILABLE: "unavailable",
            MetricState.UNSUPPORTED: "unsupported",
            MetricState.PERMISSION_DENIED: "permission denied",
            MetricState.MALFORMED: "malformed data",
            MetricState.STALE: "stale",
            MetricState.STATIC_OR_UNTRUSTED: "unverified",
        }
        return labels.get(state, str(state))

    # -- Rendering: too-small screen --

    def _draw_too_small(self, height: int, width: int) -> None:
        cy = max(0, height // 2 - 1)
        self.center_text(cy, "Terminal too small", curses.A_BOLD)
        self.center_text(
            cy + 1, f"Current: {width}x{height}  Minimum: 80x24",
        )
        self.center_text(cy + 2, "Press q to exit")

    # -- Rendering: help overlay --

    def _draw_help(self, height: int, width: int) -> None:
        start_y = max(0, (height - len(HELP_TEXT)) // 2)
        for i, line in enumerate(HELP_TEXT):
            y = start_y + i
            if y >= height - 1:
                break
            if i == 0:
                self.center_text(y, line, curses.A_BOLD)
            else:
                self.center_text(y, line)

    # -- Rendering: status line --

    def _draw_status_line(self, height: int, width: int) -> None:
        if height < 1:
            return
        y = height - 1
        screen_name = SCREEN_NAMES.get(
            self._state.active_screen, "Unknown",
        )
        parts = [f" [{self._state.active_screen}] {screen_name}"]
        if self._state.is_paused:
            parts.append(" PAUSED")
        if self._force_compact:
            parts.append(" [compact]")
        sz = self._state.last_size
        parts.append(f"  {sz[1]}x{sz[0]}")
        parts.append(f"  interval={self._collection_interval:.1f}s")
        if self._snapshot:
            ts = datetime.fromtimestamp(
                self._snapshot.captured_at, tz=UTC,
            )
            parts.append(f"  {ts.strftime('%H:%M:%S')}Z")
        parts.append("  ?=help q=quit")
        status = "".join(parts)
        self.addstr(y, 0, status[:width].ljust(width), curses.A_REVERSE)

    # -- Rendering: overview screen --

    def _draw_overview(
        self, height: int, width: int, mode: LayoutMode,
    ) -> None:
        snap = self._snapshot
        if snap is None:
            self.center_text(
                height // 2, "Collecting initial data...", curses.A_BOLD,
            )
            return

        y = 0
        y = self._draw_host_section(y, width, snap)
        y = self._draw_cpu_section(y, width, snap, mode)
        y = self._draw_memory_section(y, width, snap, mode)
        y = self._draw_thermal_section(y, width, snap, mode)
        y = self._draw_storage_section(y, width, snap, mode)
        y = self._draw_network_section(y, width, snap, mode)
        y = self._draw_power_section(y, width, snap, mode)
        y = self._draw_npu_section(y, width, snap, mode)
        self._draw_processes_section(y, width, height, snap, mode)

    # -- Host --

    def _draw_host_section(
        self, y: int, width: int, snap: DashboardSnapshot,
    ) -> int:
        host = snap.host
        title = host.hostname
        if host.model:
            title += f" — {host.model}"
        self.addstr(y, 0, title[:width], self._attr_header())
        y += 1
        info = (
            f"Kernel: {host.kernel}  "
            f"Up: {format_uptime(host.uptime_seconds)}  "
            f"Load: {host.load[0]:.2f} {host.load[1]:.2f} "
            f"{host.load[2]:.2f}"
        )
        self.addstr(y, 0, info[:width], self._attr_value())
        return y + 2

    # -- CPU --

    def _draw_cpu_section(
        self, y: int, width: int, snap: DashboardSnapshot,
        mode: LayoutMode,
    ) -> int:
        cpu_mv = snap.cpu
        if not cpu_mv.is_available or cpu_mv.value is None:
            label = f"CPU: {self._state_label(cpu_mv.state)}"
            self.addstr(y, 0, label[:width], self._attr_unavailable())
            return y + 1
        cpu = cpu_mv.value

        bar_w = min(30, max(5, width - 40))
        bar = self._make_bar(cpu.usage_percent, bar_w)
        line = f"CPU  {bar} {format_percent(cpu.usage_percent):>6}"

        # Sparkline
        spark_w = min(20, max(0, width - len(line) - 2))
        if spark_w > 3 and self._history:
            cpu_hist = [h.cpu_percent for h in self._history]
            spark = self._sparkline(cpu_hist, spark_w)
            line += f" {spark}"

        self.addstr(y, 0, line[:width], self._severity_attr(cpu.usage_percent))
        y += 1

        if mode != LayoutMode.COMPACT and cpu.cores:
            cores_per_line = 2 if width >= 100 else 1
            items: list[str] = []
            for core in cpu.cores:
                freq = ""
                if core.frequency_khz:
                    freq = format_frequency_mhz(core.frequency_khz)
                pct = format_percent(core.usage_percent)
                items.append(f"  cpu{core.core_id}: {pct:>6} {freq}")
            for i in range(0, len(items), cores_per_line):
                row = "".join(items[i:i + cores_per_line])
                self.addstr(y, 0, row[:width])
                y += 1
        return y + 1

    # -- Memory --

    def _draw_memory_section(
        self, y: int, width: int, snap: DashboardSnapshot,
        mode: LayoutMode,
    ) -> int:
        mem_mv = snap.memory
        if not mem_mv.is_available or mem_mv.value is None:
            label = f"Memory: {self._state_label(mem_mv.state)}"
            self.addstr(y, 0, label[:width], self._attr_unavailable())
            return y + 1
        mem = mem_mv.value
        bar_w = min(30, max(5, width - 40))
        bar = self._make_bar(mem.usage_percent, bar_w)
        used = format_bytes(mem.used_bytes)
        total = format_bytes(mem.total_bytes)
        line = f"MEM  {bar} {format_percent(mem.usage_percent):>6}"
        if mode != LayoutMode.COMPACT:
            line += f"  {used}/{total}"

        spark_w = min(20, max(0, width - len(line) - 2))
        if spark_w > 3 and self._history:
            mem_hist = [h.memory_percent for h in self._history]
            spark = self._sparkline(mem_hist, spark_w)
            line += f" {spark}"

        self.addstr(
            y, 0, line[:width], self._severity_attr(mem.usage_percent),
        )
        y += 1

        swap_mv = snap.swap
        if swap_mv.is_available and swap_mv.value is not None:
            swap = swap_mv.value
            if swap.total_bytes > 0:
                bar = self._make_bar(swap.usage_percent, bar_w)
                su = format_bytes(swap.used_bytes)
                st = format_bytes(swap.total_bytes)
                swp = f"SWP  {bar} {format_percent(swap.usage_percent):>6}"
                if mode != LayoutMode.COMPACT:
                    swp += f"  {su}/{st}"
                self.addstr(y, 0, swp[:width])
                y += 1
        return y + 1

    # -- Thermal --

    def _draw_thermal_section(
        self, y: int, width: int, snap: DashboardSnapshot,
        mode: LayoutMode,
    ) -> int:
        thermal_mv = snap.thermal
        if not thermal_mv.is_available or thermal_mv.value is None:
            return y
        zones = thermal_mv.value
        if not zones:
            return y
        temps = [z.temperature_c for z in zones if z.temperature_c is not None]
        max_temp = max(temps) if temps else None
        temp_str = format_temperature(max_temp)
        attr = self._temp_attr(max_temp)

        line = f"Thermal: {temp_str} max"

        spark_w = min(20, max(0, width - 30))
        if spark_w > 3 and self._history:
            temp_hist = [h.max_temperature_c for h in self._history]
            spark = self._sparkline(temp_hist, spark_w)
            line += f"  {spark}"

        self.addstr(y, 0, line[:width], attr)
        y += 1

        if mode != LayoutMode.COMPACT:
            zone_parts = []
            for z in zones[:4]:
                zone_parts.append(
                    f"  {z.name}: {format_temperature(z.temperature_c)}",
                )
            row = "".join(zone_parts)
            self.addstr(y, 0, row[:width])
            y += 1
        return y + 1

    # -- Storage --

    def _draw_storage_section(
        self, y: int, width: int, snap: DashboardSnapshot,
        mode: LayoutMode,
    ) -> int:
        self.addstr(y, 0, "Storage", self._attr_label())
        y += 1

        # Mounted filesystems
        disks_mv = snap.disks
        if disks_mv.is_available and disks_mv.value:
            limit = 2 if mode == LayoutMode.COMPACT else 4
            for disk in disks_mv.value[:limit]:
                bar_w = min(15, max(5, width - 55))
                bar = self._make_bar(disk.usage_percent, bar_w)
                used = format_bytes(disk.used_bytes)
                total = format_bytes(disk.total_bytes)
                pct = format_percent(disk.usage_percent)
                if mode == LayoutMode.COMPACT:
                    line = f"  {disk.mount:<12s} {bar} {pct:>6}"
                else:
                    line = (
                        f"  {disk.mount:<15s} {bar} {pct:>6}"
                        f"  {used}/{total}"
                    )
                self.addstr(y, 0, line[:width])
                y += 1

        # SD vs eMMC write distinction
        bio_mv = snap.block_io
        if bio_mv.is_available and bio_mv.value:
            sd_devs = [d for d in bio_mv.value if d.kind == "SD"]
            emmc_devs = [d for d in bio_mv.value if d.kind == "MMC"]
            other_devs = [
                d for d in bio_mv.value
                if d.kind not in ("SD", "MMC", None)
            ]

            if mode == LayoutMode.COMPACT:
                # Single-line compact view
                parts: list[str] = []
                for d in sd_devs:
                    parts.append(
                        f"SD: W {format_rate(d.write_bytes_per_sec)}",
                    )
                for d in emmc_devs:
                    parts.append(
                        f"eMMC: W {format_rate(d.write_bytes_per_sec)}",
                    )
                if parts:
                    self.addstr(y, 0, f"  {'  '.join(parts)}"[:width])
                    y += 1
            else:
                for d in sd_devs:
                    w_total = format_bytes(d.written_bytes_total)
                    w_rate = format_rate(d.write_bytes_per_sec)
                    line = f"  SD  {d.name:<12s} W: {w_rate:<14s} total: {w_total}"
                    spark_w = min(15, max(0, width - len(line) - 2))
                    if spark_w > 3 and self._history:
                        sd_hist: list[float | None] = [
                            h.sd_write_bytes_per_sec for h in self._history
                        ]
                        line += f" {self._sparkline(sd_hist, spark_w)}"
                    self.addstr(y, 0, line[:width])
                    y += 1
                for d in emmc_devs:
                    w_total = format_bytes(d.written_bytes_total)
                    w_rate = format_rate(d.write_bytes_per_sec)
                    line = (
                        f"  eMMC {d.name:<10s} W: {w_rate:<14s}"
                        f" total: {w_total}"
                    )
                    spark_w = min(15, max(0, width - len(line) - 2))
                    if spark_w > 3 and self._history:
                        emmc_hist: list[float | None] = [
                            h.emmc_write_bytes_per_sec
                            for h in self._history
                        ]
                        line += f" {self._sparkline(emmc_hist, spark_w)}"
                    self.addstr(y, 0, line[:width])
                    y += 1
                for d in other_devs:
                    w_rate = format_rate(d.write_bytes_per_sec)
                    w_total = format_bytes(d.written_bytes_total)
                    kind = d.kind or "?"
                    line = (
                        f"  {kind:<5s}{d.name:<10s} W: {w_rate:<14s}"
                        f" total: {w_total}"
                    )
                    self.addstr(y, 0, line[:width])
                    y += 1
        return y + 1

    # -- Network --

    def _draw_network_section(
        self, y: int, width: int, snap: DashboardSnapshot,
        mode: LayoutMode,
    ) -> int:
        net_mv = snap.network
        if not net_mv.is_available or net_mv.value is None:
            self.addstr(
                y, 0, f"Network: {self._state_label(net_mv.state)}",
                self._attr_unavailable(),
            )
            return y + 1
        interfaces = net_mv.value
        active = [i for i in interfaces if i.name != "lo"]
        if not active:
            self.addstr(y, 0, "Network: no active interface", self._attr_unavailable())
            return y + 1

        self.addstr(y, 0, "Network", self._attr_label())
        y += 1
        limit = 1 if mode == LayoutMode.COMPACT else 3
        for iface in active[:limit]:
            state = iface.operstate or "?"
            rx = format_rate(iface.rx_bytes_per_sec)
            tx = format_rate(iface.tx_bytes_per_sec)
            if mode == LayoutMode.COMPACT:
                line = f"  {iface.name} {state} RX:{rx} TX:{tx}"
            else:
                line = (
                    f"  {iface.name:<10s} {state:<6s}"
                    f"  RX: {rx:<12s}  TX: {tx}"
                )
            self.addstr(y, 0, line[:width])
            y += 1
        return y + 1

    # -- Battery / Power --

    def _draw_power_section(
        self, y: int, width: int, snap: DashboardSnapshot,
        mode: LayoutMode,
    ) -> int:
        power_mv = snap.power
        if not power_mv.is_available or power_mv.value is None:
            return y
        supplies = power_mv.value.supplies
        if not supplies:
            self.addstr(
                y, 0, "Battery: unsupported",
                self._attr_unavailable(),
            )
            return y + 1
        battery = next(
            (s for s in supplies if s.type == "Battery"), None,
        )
        if battery is None:
            self.addstr(
                y, 0, "Battery: unsupported",
                self._attr_unavailable(),
            )
            return y + 1
        cap = "—"
        if battery.capacity_percent is not None:
            cap = f"{battery.capacity_percent}%"
        status = battery.status or "unknown"
        line = f"Battery: {cap} ({status})"
        if battery.voltage_uv is not None:
            line += f"  {battery.voltage_uv / 1_000_000:.2f}V"
        if battery.current_ua is not None and mode != LayoutMode.COMPACT:
            line += f"  {battery.current_ua / 1_000:.0f}mA"
        attr = self._attr_value()
        if battery.capacity_percent is not None:
            if battery.capacity_percent <= 10:
                attr = self._attr_critical()
            elif battery.capacity_percent <= 25:
                attr = self._attr_warn()
        self.addstr(y, 0, line[:width], attr)
        return y + 2

    # -- NPU --

    def _draw_npu_section(
        self, y: int, width: int, snap: DashboardSnapshot,
        mode: LayoutMode,
    ) -> int:
        npu_mv = snap.npu
        if not npu_mv.is_available or npu_mv.value is None:
            if npu_mv.state != MetricState.AVAILABLE:
                label = f"NPU: {self._state_label(npu_mv.state)}"
                self.addstr(y, 0, label[:width], self._attr_unavailable())
                return y + 1
            return y
        npu = npu_mv.value
        if not npu.devices and npu.driver_version is None:
            self.addstr(
                y, 0, "NPU: not detected", self._attr_unavailable(),
            )
            return y + 1

        parts: list[str] = ["NPU:"]
        if npu.driver_version:
            parts.append(f" driver {npu.driver_version}")

        for dev in npu.devices:
            freq = format_frequency_mhz(dev.frequency_hz)
            # Trust handling: never show load as a gauge if untrusted
            if npu_mv.state == MetricState.STATIC_OR_UNTRUSTED:
                parts.append("  load=? (unverified)")
            elif dev.load_percent is not None:
                parts.append(f"  load={dev.load_percent}%")
            else:
                parts.append("  load=—")
            parts.append(f"  freq={freq}")
            if dev.governor and mode != LayoutMode.COMPACT:
                parts.append(f"  gov={dev.governor}")

        attr = self._attr_value()
        if npu_mv.state == MetricState.STATIC_OR_UNTRUSTED:
            attr = self._attr_warn()
        self.addstr(y, 0, "".join(parts)[:width], attr)
        return y + 2

    # -- Processes --

    def _draw_processes_section(
        self, y: int, width: int, height: int,
        snap: DashboardSnapshot, mode: LayoutMode,
    ) -> None:
        proc_mv = snap.processes
        if not proc_mv.is_available or proc_mv.value is None:
            return
        procs = proc_mv.value
        available = height - y - 1
        if available < 2:
            return
        self.addstr(
            y, 0, f"Processes: {procs.count}", self._attr_label(),
        )
        y += 1

        if mode == LayoutMode.COMPACT:
            limit = min(3, available - 1)
            for proc in procs.top_memory[:limit]:
                rss = format_bytes(proc.rss_bytes)
                cpu = f"{proc.cpu_percent:.1f}%"
                line = f"  {proc.pid:>6d} {proc.name:<16s} {cpu:>6s} {rss:>8s}"
                self.addstr(y, 0, line[:width])
                y += 1
        else:
            hdr = f"  {'PID':>7s}  {'Name':<20s}  {'CPU%':>6s}  {'RSS':>10s}  State"
            self.addstr(y, 0, hdr[:width], curses.A_UNDERLINE)
            y += 1
            limit = min(5, available - 1)
            for proc in procs.top_memory[:limit]:
                rss = format_bytes(proc.rss_bytes)
                cpu = f"{proc.cpu_percent:.1f}"
                line = (
                    f"  {proc.pid:>7d}  {proc.name:<20s}"
                    f"  {cpu:>6s}  {rss:>10s}  {proc.state}"
                )
                self.addstr(y, 0, line[:width])
                y += 1
