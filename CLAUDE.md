# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

```bash
pip install -e . pytest ruff mypy          # install with dev tools
ruff check .                                # lint
mypy rk3562deb_dashboard tests              # type check (strict mode)
python -m pytest -q                         # run all tests
python -m pytest tests/test_collectors.py -q              # run one test file
python -m pytest tests/tui/test_overview_render.py::test_name -q  # single test
```

The TUI depends on `pyTuiMonster`, a local sibling package (`../TUI_Monster`). Install with `pip install -e ".[tui]"` when working on TUI code.

## Running

```bash
python -m rk3562deb_dashboard.server --port 8765           # web dashboard
rk-tui                                                      # terminal UI (curses)
rk-tui --root tests/fixtures/healthy_rk3562 --once --ascii  # TUI with test fixtures
rk-dashboard --root tests/fixtures/healthy_rk3562           # web server with fixtures
```

The `--root` flag redirects all procfs/sysfs reads to a fixture directory, enabling development and testing on non-Rockchip machines.

## Architecture

**Two frontends, shared core:** A web dashboard (`server.py`, stdlib `http.server`) and a curses TUI (`tui/`) both consume the same `DashboardSampler` which produces typed `DashboardSnapshot` objects on a 2-second interval.

**Collectors** (`collectors/`): Each module reads one metric domain (cpu, memory, thermal, npu, etc.) from procfs/sysfs. Every collector accepts a `root: Path` parameter so reads can be redirected to fixture trees. All reads are best-effort — missing interfaces produce `MetricValue` with a non-AVAILABLE `MetricState`, never exceptions.

**Models** (`models.py`): Frozen dataclasses defining the data contract. `MetricValue[T]` wraps every metric with a `MetricState` enum (AVAILABLE, UNAVAILABLE, UNSUPPORTED, PERMISSION_DENIED, MALFORMED, STALE, STATIC_OR_UNTRUSTED) plus optional detail/source metadata.

**Sampler** (`sampler.py`): Orchestrates collectors, maintains `CollectorState` for delta calculations (CPU ticks, disk I/O rates, network throughput), and keeps a bounded in-memory ring buffer (300 points / 10 min) of `HistoryPoint` records for sparklines.

**TUI** (`tui/`): Built on `pyTuiMonster` (curses framework). `RKDashboardTui` subclasses `TuiMonsterApp`. Screens are in `tui/screens/`, widgets in `tui/widgets/`. `TuiState` tracks current screen, sort order, compact mode, etc. The `FakeScreen` test harness (`tests/tui/fake_screen.py`) replaces curses with an in-memory buffer.

**Serialization** (`serialization.py`): Converts typed snapshots to JSON dicts for the HTTP API.

## Testing

Tests use sysfs/procfs fixture trees under `tests/fixtures/` (e.g., `healthy_rk3562`, `partial_sysfs`, `malformed_metrics`). TUI tests use `FakeScreen` and the `make_app()` helper from `tests/tui/conftest.py` to render frames without a real terminal.

## Code Style

- Python 3.11+, ruff for linting (line length 100), mypy strict mode.
- `from __future__ import annotations` in every module.
- The server and collectors have zero third-party runtime dependencies (stdlib only). The TUI's only dependency is `pyTuiMonster`.
- mypy overrides disable `disallow_subclassing_any` and `disallow_untyped_decorators` for `tui/app.py` (needed for pyTuiMonster inheritance).
