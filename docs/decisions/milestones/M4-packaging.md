# Milestone 4: Packaging, documentation, and release hardening

**Status:** Not started  
**Git tag:** `milestone/M4-packaging` (created on completion)  
**Completed:** —

## Objective

Make `rk-tui` v1.0 maintainable, installable outside the development shell, and
validated on `samwise`. Confirm resource targets are met and the web dashboard
continues to work unmodified.

## Deliverables

- [ ] `pyTuiMonster` version pinned in `pyproject.toml` `[tui]` extra
- [ ] Installation instructions for development environment and `samwise`
- [ ] `docs/tui.md` — user guide: startup, keymap, screen descriptions
- [ ] `docs/metric-contract.md` — data model and availability state reference
- [ ] `docs/troubleshooting.md` — missing NPU, battery, storage path runbook
- [ ] CI addition: `pytest tests/tui/` and `rk-tui --root ... --once --ascii` smoke test
- [ ] Performance validation on `samwise` (CPU overhead, memory, zero disk writes)
- [ ] Manual acceptance test on `samwise` per the test matrix below
- [ ] Version bump to 1.0.0 in `pyproject.toml`

## Implementation choices

### Choice: pyTuiMonster version pinning
- **Options to resolve:**
  - Pin to a specific version tag (e.g., `pyTuiMonster>=0.1.0,<0.2.0`)
  - Pin to a specific git commit SHA
  - Vendor (copy) `pyTuiMonster` into the repo
- **Decision:** _Record here when resolved. Recommended: version specifier on
  a tagged release if TUI_Monster is published; otherwise git SHA pin._
- **ADR:** [ADR-002](../adr/ADR-002-tui-monster-runtime.md)

### Choice: CI integration for TUI tests
- **Chosen:** Add to the existing `.github/workflows/ci.yml`:
  ```bash
  python -m pytest -q tests/tui
  python -m rk3562deb_dashboard.tui.main \
      --root tests/fixtures/healthy_rk3562 --once --ascii
  ```
- **Rationale:** `--once --ascii` gives a headless smoke test that exercises the
  full startup/render/exit path without requiring a real terminal in CI.
- **ADR:** —

### Choice: Performance budget validation method
- **Chosen:** Measure with `top` or `pidstat` over a 60-second idle window on
  `samwise` at default 2-second refresh. Record numbers in this file.
- **Targets from spec:** < 3% CPU on one core; < 100 MiB RSS; zero periodic writes.
- **Actual measured:** _Fill in after validation._

### Choice: Documentation location
- **Chosen:** `docs/tui.md`, `docs/metric-contract.md`, `docs/troubleshooting.md`
  alongside the existing `README.md`. No separate documentation site.
- **Alternatives rejected:** GitHub Wiki — rejected because docs-in-repo means
  the docs are versioned alongside the code and available offline.
- **ADR:** —

## Manual acceptance test matrix (samwise)

| Scenario | Expected | Observed | Date |
|----------|----------|----------|------|
| Local tablet terminal session | Dashboard renders, all panels visible | | |
| SSH from Conrad, normal terminal | Dashboard renders correctly | | |
| SSH window resized wide → narrow | Reflows without restart or corruption | | |
| Terminal resized below 80×24 | Safe minimum-size message shown | | |
| Wi-Fi connected | Network panel shows interface and rates | | |
| Wi-Fi disconnected | Network panel shows down state gracefully | | |
| Battery charging | Power panel shows charging status | | |
| Battery discharging | Power panel shows capacity and current | | |
| CPU workload (stress-ng or compile) | CPU gauges and sparklines respond | | |
| Controlled write workload | SD/eMMC write panels show activity | | |
| NPU runtime available | NPU panel shows frequency/governor | | |
| NPU idle or absent | NPU panel shows unavailable cleanly | | |
| `rk-dashboard` and `rk-tui` both running | Both function independently | | |
| `q` exit | Terminal fully restored | | |
| Ctrl-C exit | Terminal fully restored | | |

## Acceptance criteria

| Criterion | Status | Notes |
|-----------|--------|-------|
| A new contributor can install and run `rk-tui` from the docs alone | — | |
| CI passes on Python 3.11 and 3.12 | — | |
| Measured idle CPU on `samwise` < 3% at 2s refresh | — | |
| Measured RSS on `samwise` < 100 MiB | — | |
| Zero writes to `/` (SD) during 60s idle run confirmed by `iostat` | — | |
| Web dashboard (`rk-dashboard`) passes existing tests unchanged | — | |
| All 14 v1.0 acceptance criteria from spec §20 are met | — | |

## Notes

_Record observations, unexpected findings, and deviations from plan here._
