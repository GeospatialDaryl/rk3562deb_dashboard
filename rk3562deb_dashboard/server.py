"""HTTP server for the local RK3562 Debian dashboard."""

from __future__ import annotations

import json
import threading
from argparse import ArgumentParser
from collections import deque
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .collectors import CollectorState, collect_snapshot

STATIC_DIR = Path(__file__).with_name("static")
SAMPLE_INTERVAL_SECONDS = 2.0
HISTORY_SIZE = 300  # 10 minutes at the default interval


def history_point(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Reduce a snapshot to the compact series the sparklines consume."""

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
    """Threaded HTTP server with a background sampler owning collector state.

    A single sampler thread collects every SAMPLE_INTERVAL_SECONDS so rates are
    computed over a steady interval regardless of how many clients poll, and a
    ring buffer of compact points feeds the history API. Requests serve the
    cached snapshot.
    """

    def __init__(
        self,
        server_address: tuple[str, int],
        root: Path = Path("/"),
        sample_interval: float = SAMPLE_INTERVAL_SECONDS,
    ) -> None:
        super().__init__(server_address, DashboardRequestHandler)
        self.root = root
        self.sample_interval = sample_interval
        self.collector_state = CollectorState()
        self.collector_lock = threading.Lock()
        self.history: deque[dict[str, Any]] = deque(maxlen=HISTORY_SIZE)
        self._latest = collect_snapshot(self.collector_state, root)
        self.history.append(history_point(self._latest))
        self._stop_sampler = threading.Event()
        self._sampler = threading.Thread(
            target=self._sample_loop, name="dashboard-sampler", daemon=True
        )
        self._sampler.start()

    def snapshot(self) -> dict[str, Any]:
        with self.collector_lock:
            return self._latest

    def history_points(self) -> dict[str, Any]:
        with self.collector_lock:
            return {"interval_seconds": self.sample_interval, "points": list(self.history)}

    def _sample_loop(self) -> None:
        while not self._stop_sampler.wait(self.sample_interval):
            snapshot = collect_snapshot(self.collector_state, self.root)
            with self.collector_lock:
                self._latest = snapshot
                self.history.append(history_point(snapshot))

    def server_close(self) -> None:
        self._stop_sampler.set()
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

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def _send_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        # Keep default useful access logs, but prefix them for journalctl readability.
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
