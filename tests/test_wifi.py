from __future__ import annotations

from rk3562deb_dashboard.wifi import (
    classify_connect_error,
    is_local,
    merge_scan,
    parse_connections,
    parse_terse,
    parse_wifi_list,
    validate_connect_request,
)


def test_parse_terse_plain() -> None:
    assert parse_terse("yes:BagNet3k5G:92:WPA2") == ["yes", "BagNet3k5G", "92", "WPA2"]


def test_parse_terse_escaped_colon_in_ssid() -> None:
    assert parse_terse(r"no:Bob\:Cafe:55:WPA2") == ["no", "Bob:Cafe", "55", "WPA2"]


def test_parse_terse_escaped_backslash() -> None:
    assert parse_terse(r"no:Back\\slash:10:") == ["no", "Back\\slash", "10", ""]


def test_parse_terse_trailing_empty_field() -> None:
    assert parse_terse("no:OpenNet:40:") == ["no", "OpenNet", "40", ""]


def test_parse_wifi_list_drops_hidden_and_bad_rows() -> None:
    stdout = "yes:Home:92:WPA2\nno::71:WPA2\nno:Weak:notanumber:WPA1\nshort:row\n"
    rows = parse_wifi_list(stdout)
    assert [row["ssid"] for row in rows] == ["Home", "Weak"]
    assert rows[0]["in_use"] is True
    assert rows[1]["signal"] == 0


def test_parse_connections_filters_wifi_type() -> None:
    stdout = "BagNet3k5G:802-11-wireless\nlo:loopback\nBob\\:Cafe:802-11-wireless\n"
    assert parse_connections(stdout) == {"BagNet3k5G", "Bob:Cafe"}


def test_merge_scan_dedupes_flags_and_sorts() -> None:
    rows = parse_wifi_list(
        "no:Dup:40:WPA2\nno:Dup:80:WPA2\nyes:Home:60:WPA2\nno:Saved:90:WPA2\nno:Strong:99:WPA2\n"
    )
    networks = merge_scan(rows, {"Home", "Saved"})
    assert [n["ssid"] for n in networks] == ["Home", "Saved", "Strong", "Dup"]
    dup = networks[-1]
    assert dup["signal"] == 80 and dup["known"] is False
    assert networks[0]["in_use"] is True and networks[0]["known"] is True


def test_classify_connect_error() -> None:
    assert classify_connect_error(4, "Error: Secrets were required, but not provided.") == (
        "wrong-password"
    )
    assert classify_connect_error(5, "Error: Timeout expired.") == "timeout"
    assert classify_connect_error(10, "Error: No network with SSID 'x' found.") == "not-found"
    assert classify_connect_error(1, "something else") == "failed"


def test_validate_connect_request() -> None:
    assert validate_connect_request("Home", None) is None
    assert validate_connect_request("Home", "12345678") is None
    assert validate_connect_request("", None) == "ssid is required"
    assert validate_connect_request(None, None) == "ssid is required"
    assert validate_connect_request("x" * 33, None) == "ssid too long"
    assert validate_connect_request("Home", "short") == "Password must be 8-63 characters"
    assert validate_connect_request("Home", "x" * 64) == "Password must be 8-63 characters"


def test_is_local() -> None:
    assert is_local(("127.0.0.1", 41234)) is True
    assert is_local(("192.168.1.50", 41234)) is False
