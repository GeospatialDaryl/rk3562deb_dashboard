# RK3562 Debian Dashboard

A local-first, btop-inspired web dashboard for Debian images running on RK3562 and related Rockchip boards. It is designed to be useful on a fresh embedded install: no Node runtime, no database, and no Python package dependencies are required for day-to-day operation.

## What it shows

The dashboard covers the same operational areas that make `btop` useful while adding board-specific Rockchip context:

- Host identity, Linux kernel, uptime, and load averages.
- CPU aggregate/core utilization and per-core cpufreq data.
- Memory, cache, and swap utilization.
- Process counts and top resident-memory processes.
- Mounted block-device usage plus read/write rates.
- Network interface state and throughput.
- Thermal zones exposed by the kernel.
- Power supplies exposed by sysfs.
- Rockchip/RK3562-specific device-tree identity, devfreq clocks, regulator rails, and eMMC/SD/NVMe storage identity.

All collectors are best-effort. If a Debian kernel does not expose a sysfs interface, the dashboard keeps running and marks that section as unavailable.

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

The UI consumes a single endpoint:

```text
GET /api/snapshot
```

The response is a JSON object with these top-level keys:

```text
timestamp, host, cpu, memory, swap, processes, disks, network, thermal, power, rockchip
```

This makes it straightforward to add terminal, kiosk, or Prometheus exporter integrations later without rewriting collectors.

## Development

```bash
python -m pytest
python -m compileall rk3562deb_dashboard tests
```

Optional static-analysis tools are configured in `pyproject.toml` when available:

```bash
ruff check .
mypy rk3562deb_dashboard tests
```

## Design notes

- **Local-first:** serves everything itself and avoids external assets; binds to `0.0.0.0` for LAN access, restrictable with `--host`.
- **Dependency-light:** the server uses only Python's standard library, which is valuable on constrained RK3562 Debian systems.
- **Safe failure mode:** collectors handle missing files and permissions without breaking the page.
- **Testable collectors:** every collector accepts an alternate filesystem root so procfs/sysfs fixtures can be tested without privileged host access.
- **Separation of concerns:** Python gathers normalized metrics; the frontend renders and refreshes the dashboard every two seconds.
