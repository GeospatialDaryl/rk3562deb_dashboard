"""Helpers for the WiFi control endpoints (parsing nmcli terse output).

Pure functions only — the server module owns the subprocess calls. nmcli's
terse (-t) format is colon-separated with backslash escaping (``\\:`` for a
literal colon inside a field, ``\\\\`` for a backslash), so splitting must
walk characters rather than use str.split/regex.
"""

from __future__ import annotations

WPA2_PSK_MIN = 8
WPA2_PSK_MAX = 63
SSID_MAX_BYTES = 32


def parse_terse(line: str) -> list[str]:
    """Split one ``nmcli -t`` line into fields, honouring backslash escapes."""
    fields: list[str] = []
    current: list[str] = []
    escaped = False
    for char in line:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
    fields.append("".join(current))
    return fields


def parse_wifi_list(stdout: str) -> list[dict[str, object]]:
    """Rows from ``nmcli -t -f ACTIVE,SSID,SIGNAL,SECURITY device wifi list``.

    Blank SSIDs (hidden networks) are dropped — out of scope for v1.
    """
    rows: list[dict[str, object]] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        fields = parse_terse(line)
        if len(fields) < 4:
            continue
        active, ssid, signal, security = fields[0], fields[1], fields[2], fields[3]
        if not ssid:
            continue
        try:
            signal_pct = int(signal)
        except ValueError:
            signal_pct = 0
        rows.append(
            {
                "ssid": ssid,
                "signal": signal_pct,
                "security": security,
                "in_use": active == "yes",
            }
        )
    return rows


def parse_connections(stdout: str) -> set[str]:
    """WiFi profile names from ``nmcli -t -f NAME,TYPE connection show``."""
    names: set[str] = set()
    for line in stdout.splitlines():
        if not line.strip():
            continue
        fields = parse_terse(line)
        if len(fields) >= 2 and fields[1] == "802-11-wireless":
            names.add(fields[0])
    return names


def merge_scan(
    scan_rows: list[dict[str, object]], known_names: set[str]
) -> list[dict[str, object]]:
    """Dedupe scan rows by SSID (keep strongest), flag known networks, sort."""
    by_ssid: dict[str, dict[str, object]] = {}
    for row in scan_rows:
        ssid = str(row["ssid"])
        existing = by_ssid.get(ssid)
        if existing is None:
            by_ssid[ssid] = dict(row)
        else:
            if int(str(row["signal"])) > int(str(existing["signal"])):
                existing["signal"] = row["signal"]
                existing["security"] = row["security"]
            existing["in_use"] = bool(existing["in_use"]) or bool(row["in_use"])
    networks = list(by_ssid.values())
    for network in networks:
        network["known"] = str(network["ssid"]) in known_names
    networks.sort(
        key=lambda n: (
            not bool(n["in_use"]),
            not bool(n["known"]),
            -int(str(n["signal"])),
            str(n["ssid"]),
        )
    )
    return networks


def classify_connect_error(returncode: int, stderr: str) -> str:
    """Map an nmcli connect failure to a stable error token for the UI."""
    lowered = stderr.lower()
    if "secrets were required" in lowered or "secrets" in lowered:
        return "wrong-password"
    if "timeout" in lowered or returncode == 5:
        return "timeout"
    if "not found" in lowered or "no network with ssid" in lowered:
        return "not-found"
    return "failed"


def validate_connect_request(ssid: object, psk: object) -> str | None:
    """Return a human-readable problem with a connect request, or None if OK."""
    if not isinstance(ssid, str) or not ssid:
        return "ssid is required"
    if len(ssid.encode("utf-8")) > SSID_MAX_BYTES:
        return "ssid too long"
    if psk is not None:
        if not isinstance(psk, str):
            return "password must be a string"
        if not (WPA2_PSK_MIN <= len(psk) <= WPA2_PSK_MAX):
            return f"Password must be {WPA2_PSK_MIN}-{WPA2_PSK_MAX} characters"
    return None


def is_local(client_address: tuple[str, int]) -> bool:
    """True when the request originated on the device itself (IPv4 bind)."""
    return client_address[0] == "127.0.0.1"
