"""UI state management for the TUI dashboard."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from enum import IntEnum, StrEnum


class ScreenId(IntEnum):
    OVERVIEW = 1
    CPU = 2
    STORAGE = 3
    NETWORK = 4
    THERMAL_POWER = 5
    NPU_ROCKCHIP = 6
    PROCESSES = 7


class ProcessSort(StrEnum):
    CPU = "cpu"
    MEMORY = "memory"
    PID = "pid"
    NAME = "name"


SCREEN_NAMES: dict[ScreenId, str] = {
    ScreenId.OVERVIEW: "Overview",
    ScreenId.CPU: "CPU",
    ScreenId.STORAGE: "Storage",
    ScreenId.NETWORK: "Network",
    ScreenId.THERMAL_POWER: "Thermal/Power",
    ScreenId.NPU_ROCKCHIP: "NPU/Rockchip",
    ScreenId.PROCESSES: "Processes",
}

SCREEN_COUNT = len(ScreenId)


@dataclass(slots=True)
class TuiState:
    active_screen: ScreenId = ScreenId.OVERVIEW
    is_paused: bool = False
    show_help: bool = False
    show_detail: bool = False
    selected_process_sort: ProcessSort = ProcessSort.CPU
    selected_interface: str | None = None
    selected_disk: str | None = None
    last_size: tuple[int, int] = (0, 0)

    def next_screen(self) -> None:
        screens = list(ScreenId)
        idx = screens.index(self.active_screen)
        self.active_screen = screens[(idx + 1) % len(screens)]

    def prev_screen(self) -> None:
        screens = list(ScreenId)
        idx = screens.index(self.active_screen)
        self.active_screen = screens[(idx - 1) % len(screens)]

    def go_to_screen(self, num: int) -> None:
        with contextlib.suppress(ValueError):
            self.active_screen = ScreenId(num)
