"""HTTP server for the local RK3562 Debian dashboard."""

from __future__ import annotations

import json
import threading
from argparse import ArgumentParser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .collectors import CollectorState, collect_snapshot

STATIC_DIR = Path(__file__).with_name("static")


class DashboardServer(ThreadingHTTPServer):
    """Threaded HTTP server that owns collector state."""

    def __init__(self, server_address: tuple[str, int], root: Path = Path("/")) -> None:
        super().__init__(server_address, DashboardRequestHandler)
        self.collector_state = CollectorState()
        self.collector_lock = threading.Lock()
        self.root = root

    def snapshot(self) -> dict[str, Any]:
        with self.collector_lock:
            return collect_snapshot(self.collector_state, self.root)


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
