# RK3562 Debian Dashboard

A local-first, btop-inspired web dashboard for Debian images running on RK3562 and related Rockchip boards. It is designed to be useful on a fresh embedded install: no Node runtime, no database, and no Python package dependencies are required for day-to-day operation.

## What it shows

The dashboard covers the same operational areas that make `btop` useful while adding board-specific Rockchip context:

- Host identity, Linux kernel, uptime, and load averages.
- CPU aggregate/core utilization and per-core cpufreq data.
- Memory, cache, and swap utilization.
- Process counts and top resident-memory processes.
- Mounted block-device usage plus read/write rates.
- Whole-device write totals since boot, separating SD cards from eMMC so SD write-reduction measures can be verified.
- Network interface state and throughput.
- Thermal zones exposed by the kernel.
- Power supplies exposed by sysfs.
- NPU clocks, governor, devfreq load, and rknpu driver version on kernels with the Rockchip NPU devfreq node. Some vendor kernels report a static load value; the UI flags it instead of showing it as live utilization.
- Rockchip/RK3562-specific device-tree identity, devfreq clocks, regulator rails, and eMMC/SD/NVMe storage identity.

All collectors are best-effort. If a Debian kernel does not expose a sysfs interface, the dashboard keeps running and marks that section as unavailable.

## Requirements

Python ≥ 3.11. No third-party runtime dependencies.

## Run locally

```bash
python -m rk3562deb_dashboard.server --port 8765
```

The server binds to `0.0.0.0` by default so the dashboard is reachable from the
LAN; open `http://<device-ip>:8765`. Pass `--host 127.0.0.1` to restrict it to
the device itself.

You can also install the console script in a virtual environment:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
rk-dashboard --port 8765
```

## Run at boot (systemd)

A unit file is provided in `deploy/`. It assumes the package is installed in a
virtual environment at `/home/frodo/venvs/dashboard`; edit `User=` and
`ExecStart=` to match your install before copying:

```bash
sudo cp deploy/rk-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rk-dashboard
```

## API

```text
GET /api/snapshot   — current metrics snapshot
GET /api/history    — 10-minute ring buffer for sparklines
GET /healthz        — {"ok": true}; used by service-readiness checks
```

The snapshot response is a JSON object with these top-level keys:

```text
timestamp, host, cpu, memory, swap, processes, disks, block_io, network, thermal, power, npu, rockchip
```

A background sampler collects every 2 seconds and keeps the last 10 minutes in
memory (never on disk). `/api/history` returns `{"interval_seconds": 2, "points": [...]}` where each point is `{t, cpu, mem, temp, sd_write, emmc_write}`, which the UI renders as sparklines on the CPU, thermal, and storage cards.

This makes it straightforward to add terminal, kiosk, or Prometheus exporter integrations later without rewriting collectors.

## Development

```bash
pip install -e . pytest ruff mypy
python -m compileall rk3562deb_dashboard tests
ruff check .
mypy rk3562deb_dashboard tests
python -m pytest -q
```

CI runs the same steps on every push (`.github/workflows/ci.yml`).

The `--root` flag lets you point the server at a directory of procfs/sysfs
fixtures instead of `/`, which is how the test suite exercises collectors
without privileged host access:

```bash
rk-dashboard --root tests/fixtures/
```

## Design notes

- **Local-first:** serves everything itself and avoids external assets; binds to `0.0.0.0` for LAN access, restrictable with `--host`.
- **Dependency-light:** the server uses only Python's standard library, which is valuable on constrained RK3562 Debian systems.
- **Safe failure mode:** collectors handle missing files and permissions without breaking the page.
- **Testable collectors:** every collector accepts an alternate filesystem root so procfs/sysfs fixtures can be tested without privileged host access.
- **Separation of concerns:** Python gathers normalized metrics; the frontend renders and refreshes the dashboard every two seconds.
- **RAM-only history:** the 10-minute metric history lives in a fixed-size in-memory ring buffer, consistent with keeping the SD card free of write traffic.
