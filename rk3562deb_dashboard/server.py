"""HTTP server for the local RK3562 Debian dashboard."""

from __future__ import annotations

import json
import subprocess
from argparse import ArgumentParser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .sampler import SAMPLE_INTERVAL_SECONDS, DashboardSampler
from .serialization import history_point_to_dict, snapshot_to_dict

STATIC_DIR = Path(__file__).with_name("static")

# Fixed allow-list of systemctl invocations the dashboard may trigger.
# Each entry is authorized narrowly by a matching polkit rule (see
# packaging/49-samwise-dashboard-ctl.rules) so the unprivileged dashboard
# process can request exactly these actions without sudo/setuid (blocked
# anyway by NoNewPrivileges=true on this service).
CONTROL_ACTIONS: dict[str, list[str]] = {
    "kiosk-restart": ["systemctl", "restart", "dashboard-kiosk-cog.service"],
    "sd-backup": ["systemctl", "start", "sd-backup.service"],
    "switch-camera-cv": ["systemctl", "start", "camera-cv.service"],
    "switch-dashboard": ["systemctl", "start", "dashboard-kiosk-cog.service"],
}


# Keep the old dict-based helper for backward compatibility with tests
def history_point(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Reduce a snapshot dict to the compact series the sparklines consume."""
    temps = [
        zone["temperature_c"]
        for zone in snapshot.get("thermal", [])
        if zone.get("temperature_c") is not None
    ]
    sd_write = emmc_write = None
    for device in snapshot.get("block_io", []):
        if device.get("kind") == "SD" and sd_write is None:
            sd_write = device["write_bytes_per_sec"]
        elif device.get("kind") == "MMC" and emmc_write is None:
            emmc_write = device["write_bytes_per_sec"]
    return {
        "t": snapshot["timestamp"],
        "cpu": snapshot["cpu"]["total"].get("usage_percent"),
        "mem": snapshot["memory"].get("usage_percent"),
        "temp": max(temps) if temps else None,
        "sd_write": sd_write,
        "emmc_write": emmc_write,
    }


class DashboardServer(ThreadingHTTPServer):
    """Threaded HTTP server backed by a DashboardSampler.

    The sampler owns the collector state and background thread.  This class
    translates typed snapshots into JSON dicts for the existing browser UI.
    """

    def __init__(
        self,
        server_address: tuple[str, int],
        root: Path = Path("/"),
        sample_interval: float = SAMPLE_INTERVAL_SECONDS,
    ) -> None:
        super().__init__(server_address, DashboardRequestHandler)
        self.sampler = DashboardSampler(root=root, interval=sample_interval)
        self.sampler.start()

    def snapshot(self) -> dict[str, Any]:
        return snapshot_to_dict(self.sampler.sample())

    def history_points(self) -> dict[str, Any]:
        return {
            "interval_seconds": self.sampler.interval,
            "points": [history_point_to_dict(hp) for hp in self.sampler.history()],
        }

    def server_close(self) -> None:
        if hasattr(self, "sampler"):
            self.sampler.stop()
        super().server_close()


class DashboardRequestHandler(SimpleHTTPRequestHandler):
    """Serve static assets plus JSON metrics API."""

    server: DashboardServer

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - stdlib hook name
        parsed = urlparse(self.path)
        if parsed.path == "/api/snapshot":
            self._send_json(self.server.snapshot())
            return
        if parsed.path == "/api/history":
            self._send_json(self.server.history_points())
            return
        if parsed.path == "/healthz":
            self._send_json({"ok": True})
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802 - stdlib hook name
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/control/"):
            action = parsed.path.removeprefix("/api/control/")
            self._run_control_action(action)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _run_control_action(self, action: str) -> None:
        command = CONTROL_ACTIONS.get(action)
        if command is None:
            self._send_json({"ok": False, "error": "unknown action"}, status=HTTPStatus.NOT_FOUND)
            return
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=15, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
            return
        ok = result.returncode == 0
        self._send_json(
            {"ok": ok, "returncode": result.returncode, "stderr": result.stderr.strip()},
            status=HTTPStatus.OK if ok else HTTPStatus.BAD_GATEWAY,
        )

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        super().log_message("[rk-dashboard] " + format, *args)


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Run the local RK3562 Debian dashboard")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", default=8765, type=int, help="Bind port (default: 8765)")
    parser.add_argument(
        "--root",
        default="/",
        type=Path,
        help="Filesystem root to read metrics from; useful for tests (default: /)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    server = DashboardServer((args.host, args.port), args.root)
    url = f"http://{args.host if args.host != '0.0.0.0' else '127.0.0.1'}:{args.port}"
    print(f"RK3562 Debian dashboard listening on {url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
