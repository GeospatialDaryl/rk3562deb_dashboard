"""RKDashboardTui application shell over TuiMonsterApp."""

from __future__ import annotations

import curses
import time

from pyTuiMonster import TuiConfig, TuiMonsterApp, key_binding

from ..models import DashboardSnapshot
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
from .state import SCREEN_NAMES, ScreenId, TuiState

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
            self._last_collection = now

    @key_binding(ord("d"))
    def _toggle_detail(self, _key: int) -> None:
        self._state.show_detail = not self._state.show_detail

    @key_binding(ord("c"))
    def _toggle_compact(self, _key: int) -> None:
        self._force_compact = not self._force_compact

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

    @key_binding(ord("1"), ord("2"), ord("3"), ord("4"), ord("5"), ord("6"), ord("7"))
    def _switch_screen(self, key: int) -> None:
        self._state.go_to_screen(key - ord("0"))

    # -- Lifecycle --

    def on_start(self) -> None:
        self._init_colors()
        self._snapshot = self._sampler.sample_now()
        self._last_collection = time.monotonic()

    def update(self) -> None:
        if self._state.is_paused:
            return
        now = time.monotonic()
        if now - self._last_collection >= self._collection_interval:
            self._snapshot = self._sampler.sample_now()
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
            curses.init_pair(1, curses.COLOR_GREEN, -1)    # normal/good
            curses.init_pair(2, curses.COLOR_YELLOW, -1)   # attention/warning
            curses.init_pair(3, curses.COLOR_RED, -1)      # critical
            curses.init_pair(4, curses.COLOR_CYAN, -1)     # header/label
            curses.init_pair(5, curses.COLOR_MAGENTA, -1)  # unavailable
            curses.init_pair(6, curses.COLOR_WHITE, -1)    # dim/secondary
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

    # -- Rendering: too-small screen --

    def _draw_too_small(self, height: int, width: int) -> None:
        msg1 = "Terminal too small"
        msg2 = f"Current: {width}x{height}  Minimum: 80x24"
        msg3 = "Press q to exit"
        cy = max(0, height // 2 - 1)
        self.center_text(cy, msg1, curses.A_BOLD)
        self.center_text(cy + 1, msg2)
        self.center_text(cy + 2, msg3)

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
        screen_name = SCREEN_NAMES.get(self._state.active_screen, "Unknown")
        parts = [f" [{self._state.active_screen}] {screen_name}"]
        if self._state.is_paused:
            parts.append(" PAUSED")
        parts.append(f"  {self._state.last_size[1]}x{self._state.last_size[0]}")
        parts.append(f"  interval={self._collection_interval:.1f}s")
        parts.append("  ?=help q=quit")
        status = "".join(parts)
        self.addstr(y, 0, status[:width].ljust(width), curses.A_REVERSE)

    # -- Rendering: overview screen --

    def _draw_overview(self, height: int, width: int, mode: LayoutMode) -> None:
        snap = self._snapshot
        if snap is None:
            self.center_text(height // 2, "Collecting initial data...", curses.A_BOLD)
            return

        y = 0
        y = self._draw_host_section(y, width, snap)
        y = self._draw_cpu_section(y, width, snap, mode)
        y = self._draw_memory_section(y, width, snap)
        y = self._draw_thermal_section(y, width, snap, mode)
        y = self._draw_storage_section(y, width, snap, mode)
        y = self._draw_network_section(y, width, snap, mode)
        y = self._draw_power_section(y, width, snap, mode)
        y = self._draw_npu_section(y, width, snap, mode)
        self._draw_processes_section(y, width, height, snap, mode)

    def _draw_host_section(self, y: int, width: int, snap: DashboardSnapshot) -> int:
        host = snap.host
        title = host.hostname
        if host.model:
            title += f" — {host.model}"
        self.addstr(y, 0, title[:width], self._attr_header())
        y += 1
        info = (
            f"Kernel: {host.kernel}  "
            f"Up: {format_uptime(host.uptime_seconds)}  "
            f"Load: {host.load[0]:.2f} {host.load[1]:.2f} {host.load[2]:.2f}"
        )
        self.addstr(y, 0, info[:width], self._attr_value())
        return y + 2

    def _draw_cpu_section(
        self, y: int, width: int, snap: DashboardSnapshot, mode: LayoutMode
    ) -> int:
        cpu_mv = snap.cpu
        if not cpu_mv.is_available or cpu_mv.value is None:
            self.addstr(y, 0, "CPU: unavailable", self._attr_unavailable())
            return y + 1
        cpu = cpu_mv.value
        bar_width = min(30, width - 25)
        bar = bar_gauge(cpu.usage_percent, bar_width) if not self._ascii_only else \
            bar_gauge(cpu.usage_percent, bar_width, "#", "-")
        line = f"CPU  {bar} {format_percent(cpu.usage_percent):>6}"
        self.addstr(y, 0, line[:width], self._cpu_attr(cpu.usage_percent))
        y += 1

        if mode != LayoutMode.COMPACT and cpu.cores:
            cores_per_line = 2 if width >= 100 else 1
            core_items = []
            for core in cpu.cores:
                freq = format_frequency_mhz(core.frequency_khz) if core.frequency_khz else ""
                core_items.append(
                    f"  cpu{core.core_id}: {format_percent(core.usage_percent):>6} {freq}"
                )
            for i in range(0, len(core_items), cores_per_line):
                line = "".join(core_items[i:i + cores_per_line])
                self.addstr(y, 0, line[:width])
                y += 1
        return y + 1

    def _cpu_attr(self, percent: float) -> int:
        if percent >= 90:
            return self._attr_critical()
        if percent >= 70:
            return self._attr_warn()
        return self._attr_good()

    def _draw_memory_section(self, y: int, width: int, snap: DashboardSnapshot) -> int:
        mem_mv = snap.memory
        if not mem_mv.is_available or mem_mv.value is None:
            self.addstr(y, 0, "Memory: unavailable", self._attr_unavailable())
            return y + 1
        mem = mem_mv.value
        bar_width = min(30, width - 25)
        bar = bar_gauge(mem.usage_percent, bar_width) if not self._ascii_only else \
            bar_gauge(mem.usage_percent, bar_width, "#", "-")
        used = format_bytes(mem.used_bytes)
        total = format_bytes(mem.total_bytes)
        line = f"MEM  {bar} {format_percent(mem.usage_percent):>6}  {used}/{total}"
        self.addstr(y, 0, line[:width], self._cpu_attr(mem.usage_percent))
        y += 1

        swap_mv = snap.swap
        if swap_mv.is_available and swap_mv.value is not None:
            swap = swap_mv.value
            if swap.total_bytes > 0:
                bar = bar_gauge(swap.usage_percent, bar_width) if not self._ascii_only else \
                    bar_gauge(swap.usage_percent, bar_width, "#", "-")
                used = format_bytes(swap.used_bytes)
                total = format_bytes(swap.total_bytes)
                line = f"SWP  {bar} {format_percent(swap.usage_percent):>6}  {used}/{total}"
                self.addstr(y, 0, line[:width])
                y += 1
        return y + 1

    def _draw_thermal_section(
        self, y: int, width: int, snap: DashboardSnapshot, mode: LayoutMode
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
        attr = self._attr_value()
        if max_temp is not None:
            if max_temp >= 80:
                attr = self._attr_critical()
            elif max_temp >= 60:
                attr = self._attr_warn()
        self.addstr(y, 0, f"Thermal: {temp_str} max", attr)
        if mode != LayoutMode.COMPACT:
            zone_parts = [f"  {z.name}: {format_temperature(z.temperature_c)}" for z in zones[:4]]
            self.addstr(y, 22, "".join(zone_parts)[:width - 22])
        return y + 2

    def _draw_storage_section(
        self, y: int, width: int, snap: DashboardSnapshot, mode: LayoutMode
    ) -> int:
        self.addstr(y, 0, "Storage", self._attr_label())
        y += 1

        disks_mv = snap.disks
        if disks_mv.is_available and disks_mv.value:
            for disk in disks_mv.value[:4]:
                bar_width = min(20, width - 50)
                bar = bar_gauge(disk.usage_percent, bar_width) if not self._ascii_only else \
                    bar_gauge(disk.usage_percent, bar_width, "#", "-")
                line = (
                    f"  {disk.mount:<15s} {bar} {format_percent(disk.usage_percent):>6}"
                    f"  {format_bytes(disk.used_bytes)}/{format_bytes(disk.total_bytes)}"
                )
                self.addstr(y, 0, line[:width])
                y += 1

        bio_mv = snap.block_io
        if bio_mv.is_available and bio_mv.value:
            for dev in bio_mv.value:
                kind = dev.kind or "?"
                line = (
                    f"  {dev.name} ({kind})"
                    f"  W: {format_rate(dev.write_bytes_per_sec)}"
                    f"  total: {format_bytes(dev.written_bytes_total)}"
                )
                self.addstr(y, 0, line[:width])
                y += 1
        return y + 1

    def _draw_network_section(
        self, y: int, width: int, snap: DashboardSnapshot, mode: LayoutMode
    ) -> int:
        net_mv = snap.network
        if not net_mv.is_available or net_mv.value is None:
            return y
        interfaces = net_mv.value
        if not interfaces:
            return y
        active = [i for i in interfaces if i.name != "lo"]
        if not active:
            return y
        self.addstr(y, 0, "Network", self._attr_label())
        y += 1
        for iface in active[:3]:
            state = iface.operstate or "?"
            line = (
                f"  {iface.name:<10s} {state:<6s}"
                f"  RX: {format_rate(iface.rx_bytes_per_sec):<12s}"
                f"  TX: {format_rate(iface.tx_bytes_per_sec)}"
            )
            self.addstr(y, 0, line[:width])
            y += 1
        return y + 1

    def _draw_power_section(
        self, y: int, width: int, snap: DashboardSnapshot, mode: LayoutMode
    ) -> int:
        power_mv = snap.power
        if not power_mv.is_available or power_mv.value is None:
            return y
        supplies = power_mv.value.supplies
        if not supplies:
            return y
        battery = next((s for s in supplies if s.type == "Battery"), None)
        if battery is None:
            return y
        cap = f"{battery.capacity_percent}%" if battery.capacity_percent is not None else "—"
        status = battery.status or "unknown"
        line = f"Battery: {cap} ({status})"
        if battery.voltage_uv is not None:
            line += f"  {battery.voltage_uv / 1_000_000:.2f}V"
        self.addstr(y, 0, line[:width])
        return y + 2

    def _draw_npu_section(
        self, y: int, width: int, snap: DashboardSnapshot, mode: LayoutMode
    ) -> int:
        npu_mv = snap.npu
        if not npu_mv.is_available or npu_mv.value is None:
            return y
        npu = npu_mv.value
        if not npu.devices and npu.driver_version is None:
            self.addstr(y, 0, "NPU: not detected", self._attr_unavailable())
            return y + 1
        parts = ["NPU:"]
        if npu.driver_version:
            parts.append(f" driver {npu.driver_version}")
        for dev in npu.devices:
            freq = format_frequency_mhz(dev.frequency_hz)
            if dev.load_percent is not None:
                parts.append(f"  load={dev.load_percent}%")
            parts.append(f"  freq={freq}")
            if dev.governor:
                parts.append(f"  gov={dev.governor}")
        self.addstr(y, 0, "".join(parts)[:width])
        return y + 2

    def _draw_processes_section(
        self, y: int, width: int, height: int, snap: DashboardSnapshot, mode: LayoutMode
    ) -> None:
        proc_mv = snap.processes
        if not proc_mv.is_available or proc_mv.value is None:
            return
        procs = proc_mv.value
        available_lines = height - y - 1  # leave room for status line
        if available_lines < 2:
            return
        self.addstr(y, 0, f"Processes: {procs.count}", self._attr_label())
        y += 1
        header = f"  {'PID':>7s}  {'Name':<20s}  {'RSS':>10s}  {'State'}"
        self.addstr(y, 0, header[:width], curses.A_UNDERLINE)
        y += 1
        for proc in procs.top_memory[:min(8, available_lines - 1)]:
            rss = format_bytes(proc.rss_bytes)
            line = f"  {proc.pid:>7d}  {proc.name:<20s}  {rss:>10s}  {proc.state}"
            self.addstr(y, 0, line[:width])
            y += 1
