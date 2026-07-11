"""CLI entry point for the rk-tui terminal dashboard."""

from __future__ import annotations

import contextlib
import json
import sys
from argparse import ArgumentParser
from pathlib import Path

from ..collectors import CollectorState, collect_snapshot
from ..sampler import DashboardSampler
from ..serialization import snapshot_to_dict
from .app import RKDashboardTui
from .crashlog import install_crash_handler


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        prog="rk-tui",
        description="Terminal dashboard for RK3562 Debian devices",
    )
    parser.add_argument(
        "--interval", type=float, default=2.0,
        help="Refresh interval in seconds (default: 2.0, range: 0.5-10.0)",
    )
    parser.add_argument(
        "--root", type=Path, default=Path("/"),
        help="Alternate procfs/sysfs root for testing",
    )
    parser.add_argument(
        "--screen", default="overview",
        choices=["overview", "cpu", "storage", "network",
                 "thermal-power", "npu-rockchip", "processes"],
        help="Initial screen",
    )
    parser.add_argument("--no-color", action="store_true", help="Disable terminal colors")
    parser.add_argument("--ascii", action="store_true", help="Force ASCII gauges and sparklines")
    parser.add_argument(
        "--once", action="store_true",
        help="Render a single snapshot then exit",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit one snapshot as JSON and exit",
    )
    parser.add_argument("--debug", action="store_true", help="Enable diagnostic logging to stderr")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    return parser


SCREEN_MAP = {
    "overview": 1,
    "cpu": 2,
    "storage": 3,
    "network": 4,
    "thermal-power": 5,
    "npu-rockchip": 6,
    "processes": 7,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    install_crash_handler()

    if args.version:
        from .. import __version__
        print(f"rk-tui {__version__}")
        sys.exit(0)

    interval = max(0.5, min(10.0, args.interval))

    if args.json:
        state = CollectorState()
        snapshot = collect_snapshot(state, args.root)
        json.dump(snapshot_to_dict(snapshot), sys.stdout, indent=2)
        print()
        sys.exit(0)

    sampler = DashboardSampler(root=args.root, interval=interval)

    app = RKDashboardTui(
        sampler=sampler,
        interval=interval,
        once=args.once,
        no_color=args.no_color,
        ascii_only=args.ascii,
    )

    screen_num = SCREEN_MAP.get(args.screen, 1)
    app._state.go_to_screen(screen_num)

    with contextlib.suppress(KeyboardInterrupt):
        app.run()


if __name__ == "__main__":
    main()
