"""HTTP server for the local RK3562 Debian dashboard."""

from __future__ import annotations

import json
import os
import subprocess
from argparse import ArgumentParser
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import wifi
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
    "transcribe-start": ["systemctl", "start", "audio-transcribe.service"],
    "transcribe-stop": ["systemctl", "stop", "audio-transcribe.service"],
    "display-off": ["systemctl", "start", "display-off.service"],
    "switch-mapping": ["systemctl", "start", "mapping-cv.service"],
    # Deviates from the systemctl-only shape (see ADR-007): still a fixed
    # argv, authorized by polkit rule 51- via power-profiles-daemon.
    "power-toggle": ["/home/frodo/bin/power-toggle"],
}

# Screen-owning apps the launcher can report on / switch to.  Mirrors
# ~/build/app-switcher/apps.json plus the display-off oneshot; systemd
# Conflicts= guarantees at most one is active.
APP_UNITS: dict[str, str] = {
    "dashboard": "dashboard-kiosk-cog.service",
    "camera-cv": "camera-cv.service",
    "mapping": "mapping-cv.service",
    "display-off": "display-off.service",
}

# CV demos selectable from the launcher.  Source of truth is the DEMOS list
# in ~/src/camera-npu/demos/__init__.py (cam_detect.py validates unknown
# names anyway); kept as a literal here to avoid a cross-repo import.
CV_DEMOS: tuple[str, ...] = (
    "yolov8",
    "resnet",
    "yolov5",
    "yolov6",
    "yolov7",
    "yolo11",
    "ppyoloe",
    "yolov10",
    "yolox",
    "yolov8_pose",
    "RetinaFace",
    "LPRNet",
    "yolov8_seg",
    "yolov5_seg",
    "ppseg",
    "mobilenet",
    "PPOCR_Det",
    "PPOCR_Rec",
    "deeplabv3",
    "yolov8_obb",
)


def runtime_dir() -> Path:
    """The per-user runtime dir where cam_detect's demo state file lives."""
    return Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")


WIFI_DEVICE = "wlan0"


def _nmcli(args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["nmcli", *args], capture_output=True, text=True, timeout=timeout, check=False
    )


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
        if parsed.path == "/api/launcher-status":
            self._send_json(self._launcher_status())
            return
        if parsed.path == "/api/wifi/status":
            self._send_json(self._wifi_status())
            return
        if parsed.path == "/api/wifi/scan":
            rescan = parse_qs(parsed.query).get("rescan", ["no"])[0] == "yes"
            self._wifi_scan(rescan)
            return
        # The launcher is the kiosk home page (ADR-007); the metrics
        # dashboard moved to /dashboard.
        if parsed.path == "/":
            self.path = "/launcher.html"
        elif parsed.path == "/dashboard":
            self.path = "/index.html"
        elif parsed.path == "/wifi":
            self.path = "/wifi.html"
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802 - stdlib hook name
        parsed = urlparse(self.path)
        # Every POST changes device state (services, screen owner, WiFi,
        # demo selection) — all of it is only accepted from the device
        # itself. The LAN gets the read-only GET surface. (2026-07-12
        # stability review; previously only WiFi writes were guarded.)
        if not wifi.is_local(self.client_address):
            self._send_json(
                {"ok": False, "error": "state changes are only accepted from the device"},
                status=HTTPStatus.FORBIDDEN,
            )
            return
        if parsed.path.startswith("/api/wifi/"):
            self._wifi_post(parsed.path.removeprefix("/api/wifi/"))
            return
        if parsed.path == "/api/control/set-cv-demo":
            self._set_cv_demo()
            return
        if parsed.path.startswith("/api/control/"):
            action = parsed.path.removeprefix("/api/control/")
            self._run_control_action(action)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _set_cv_demo(self) -> None:
        """Write the demo state file cam_detect.py polls (plain file, no privilege)."""
        body = self._read_json_body()
        if body is None:
            self._send_json(
                {"ok": False, "error": "invalid JSON body"}, status=HTTPStatus.BAD_REQUEST
            )
            return
        demo = body.get("demo")
        if demo not in CV_DEMOS:
            self._send_json(
                {"ok": False, "error": "unknown demo"}, status=HTTPStatus.BAD_REQUEST
            )
            return
        state_file = runtime_dir() / "cv-demo-current"
        try:
            state_file.write_text(f"{demo}\n")
        except OSError as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
            return
        self._send_json({"ok": True, "demo": demo})

    def _read_json_body(self) -> dict[str, Any] | None:
        """Parse the request body as a JSON object; None when malformed."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return None
        return body if isinstance(body, dict) else None

    def _wifi_status(self) -> dict[str, Any]:
        status: dict[str, Any] = {
            "radio": None,
            "device_state": None,
            "ssid": None,
            "signal": None,
            "ip4": None,
        }
        try:
            radio = _nmcli(["-t", "-f", "WIFI", "radio"], timeout=5)
            if radio.returncode == 0:
                status["radio"] = radio.stdout.strip()
            show = _nmcli(
                [
                    "-t",
                    "-f",
                    "GENERAL.CONNECTION,GENERAL.STATE,IP4.ADDRESS",
                    "device",
                    "show",
                    WIFI_DEVICE,
                ],
                timeout=5,
            )
            if show.returncode == 0:
                for line in show.stdout.splitlines():
                    fields = wifi.parse_terse(line)
                    if len(fields) < 2:
                        continue
                    key, value = fields[0], fields[1]
                    if key == "GENERAL.CONNECTION" and value:
                        status["ssid"] = value
                    elif key == "GENERAL.STATE":
                        status["device_state"] = value
                    elif key.startswith("IP4.ADDRESS") and status["ip4"] is None:
                        status["ip4"] = value
            cached = _nmcli(
                ["-t", "-f", "ACTIVE,SSID,SIGNAL,SECURITY", "device", "wifi", "list",
                 "--rescan", "no"],
                timeout=5,
            )
            if cached.returncode == 0:
                for row in wifi.parse_wifi_list(cached.stdout):
                    if row["in_use"]:
                        status["signal"] = row["signal"]
                        break
        except (OSError, subprocess.TimeoutExpired):
            pass
        return status

    def _known_wifi_names(self) -> set[str]:
        result = _nmcli(["-t", "-f", "NAME,TYPE", "connection", "show"], timeout=5)
        return wifi.parse_connections(result.stdout) if result.returncode == 0 else set()

    def _wifi_scan(self, rescan: bool) -> None:
        try:
            scan = _nmcli(
                ["-t", "-f", "ACTIVE,SSID,SIGNAL,SECURITY", "device", "wifi", "list",
                 "--rescan", "yes" if rescan else "no"],
                timeout=25 if rescan else 5,
            )
            known = self._known_wifi_names()
        except (OSError, subprocess.TimeoutExpired) as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
            return
        if scan.returncode != 0:
            self._send_json(
                {"ok": False, "error": scan.stderr.strip() or "scan failed"},
                status=HTTPStatus.BAD_GATEWAY,
            )
            return
        networks = wifi.merge_scan(wifi.parse_wifi_list(scan.stdout), known)
        self._send_json({"ok": True, "networks": networks})

    def _wifi_post(self, action: str) -> None:
        # Localhost enforcement happens for every POST in do_POST.
        body = self._read_json_body()
        if body is None:
            self._send_json(
                {"ok": False, "error": "invalid JSON body"}, status=HTTPStatus.BAD_REQUEST
            )
            return
        if action == "connect":
            self._wifi_connect(body)
        elif action == "forget":
            self._wifi_forget(body)
        else:
            self._send_json(
                {"ok": False, "error": "unknown action"}, status=HTTPStatus.NOT_FOUND
            )

    def _wifi_connect(self, body: dict[str, Any]) -> None:
        ssid = body.get("ssid")
        psk = body.get("psk") or None
        problem = wifi.validate_connect_request(ssid, psk)
        if problem is not None:
            self._send_json({"ok": False, "error": problem}, status=HTTPStatus.BAD_REQUEST)
            return
        assert isinstance(ssid, str)
        try:
            known_before = self._known_wifi_names()
            if ssid in known_before and psk is None:
                argv = ["--wait", "40", "connection", "up", "id", ssid]
            else:
                argv = ["--wait", "40", "device", "wifi", "connect", ssid]
                if psk is not None:
                    argv += ["password", psk]
            result = _nmcli(argv, timeout=45)
            if result.returncode == 0:
                self._send_json({"ok": True, "ssid": ssid})
                return
            # A failed first join leaves a half-configured profile behind,
            # which would make the retry take the known-network path and
            # fail differently; delete it so retries are clean.
            if ssid not in known_before and ssid in self._known_wifi_names():
                _nmcli(["connection", "delete", "id", ssid], timeout=10)
            detail = result.stderr.strip() or result.stdout.strip()
            self._send_json(
                {
                    "ok": False,
                    "error": wifi.classify_connect_error(result.returncode, result.stderr),
                    "detail": detail.splitlines()[0] if detail else "",
                },
                status=HTTPStatus.BAD_GATEWAY,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)

    def _wifi_forget(self, body: dict[str, Any]) -> None:
        name = body.get("name")
        if not isinstance(name, str) or not name:
            self._send_json(
                {"ok": False, "error": "name is required"}, status=HTTPStatus.BAD_REQUEST
            )
            return
        try:
            result = _nmcli(["connection", "delete", "id", name], timeout=10)
        except (OSError, subprocess.TimeoutExpired) as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
            return
        ok = result.returncode == 0
        self._send_json(
            {"ok": ok, "error": None if ok else (result.stderr.strip() or "delete failed")},
            status=HTTPStatus.OK if ok else HTTPStatus.BAD_GATEWAY,
        )

    def _launcher_status(self) -> dict[str, Any]:
        active_app = None
        for name, unit in APP_UNITS.items():
            try:
                result = subprocess.run(
                    ["systemctl", "is-active", "--quiet", unit], timeout=5, check=False
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
            if result.returncode == 0:
                active_app = name
                break
        battery: dict[str, Any] = {"status": None, "capacity_percent": None}
        supply = self.server.sampler.root / "sys/class/power_supply/battery"
        try:
            battery["status"] = (supply / "status").read_text().strip()
            battery["capacity_percent"] = int((supply / "capacity").read_text().strip())
        except (OSError, ValueError):
            pass
        power_profile = None
        try:
            profile_result = subprocess.run(
                ["powerprofilesctl", "get"], capture_output=True, text=True, timeout=5, check=False
            )
            if profile_result.returncode == 0:
                power_profile = profile_result.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
        cv_demo = None
        try:
            name = (runtime_dir() / "cv-demo-current").read_text().strip()
            cv_demo = name if name in CV_DEMOS else None
        except OSError:
            pass
        wifi_summary: dict[str, Any] = {"ssid": None, "signal": None}
        try:
            cached = _nmcli(
                ["-t", "-f", "ACTIVE,SSID,SIGNAL,SECURITY", "device", "wifi", "list",
                 "--rescan", "no"],
                timeout=5,
            )
            if cached.returncode == 0:
                for row in wifi.parse_wifi_list(cached.stdout):
                    if row["in_use"]:
                        wifi_summary = {"ssid": row["ssid"], "signal": row["signal"]}
                        break
        except (OSError, subprocess.TimeoutExpired):
            pass
        return {
            "active_app": active_app,
            "battery": battery,
            "power_profile": power_profile,
            "cv_demo": cv_demo,
            "cv_demos": list(CV_DEMOS),
            "wifi": wifi_summary,
        }

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
