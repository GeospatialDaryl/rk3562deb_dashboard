"""Human-readable formatting for metric values."""

from __future__ import annotations


def format_bytes(value: int) -> str:
    if value < 0:
        return f"-{format_bytes(-value)}"
    if value < 1024:
        return f"{value} B"
    for unit in ("KiB", "MiB", "GiB", "TiB"):
        value_f = value / 1024
        if value_f < 1024 or unit == "TiB":
            return f"{value_f:.1f} {unit}"
        value = int(value_f)
    return f"{value} B"


def format_rate(bytes_per_sec: int) -> str:
    return f"{format_bytes(bytes_per_sec)}/s"


def format_percent(value: float) -> str:
    return f"{value:.1f}%"


def format_temperature(celsius: float | None) -> str:
    if celsius is None:
        return "—"
    return f"{celsius:.1f}°C"


def format_frequency_mhz(hz: int | None) -> str:
    if hz is None:
        return "—"
    return f"{hz / 1_000_000:.0f} MHz"


def format_uptime(seconds: float) -> str:
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def bar_gauge(percent: float, width: int, filled: str = "█", empty: str = "░") -> str:
    if width <= 0:
        return ""
    fill = int(round(percent / 100.0 * width))
    fill = max(0, min(width, fill))
    return filled * fill + empty * (width - fill)
