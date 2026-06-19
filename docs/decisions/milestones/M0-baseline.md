# Milestone 0: Baseline assessment and contract freeze

**Status:** Not started  
**Git tag:** `milestone/M0-baseline` (created on completion)  
**Completed:** —

## Objective

Establish a stable, shared data model and sampler abstraction before any terminal
rendering begins. The web dashboard must continue to work without regression.

## Deliverables

- [ ] Audit current collector/sampler/public API module boundaries
- [ ] Add `models.py` with typed `DashboardSnapshot`, `MetricValue[T]`, `MetricState`
- [ ] Add `availability.py` with availability and freshness helpers
- [ ] Extract `DashboardSampler` from `DashboardServer` into standalone `sampler.py`
- [ ] Update `DashboardServer` to use the extracted sampler (no behavior change)
- [ ] Refactor `collectors.py` into `collectors/` subpackage (one file per domain)
- [ ] Add contract tests that assert the snapshot shape consumed by the web dashboard
- [ ] Create `tests/fixtures/` directory tree (see fixture scenarios below)
- [ ] Confirm `ruff`, `mypy`, and `pytest` pass after refactor

## Implementation choices

### Choice: Collector subpackage structure
- **Chosen:** `collectors/base.py`, `collectors/cpu.py`, etc. (separate file per domain)
- **Rationale:** Matches spec §9; allows domain-specific imports without pulling
  in the entire collector surface; makes it easier to add new collectors without
  touching a shared file.
- **Alternatives rejected:** Keep single `collectors.py` — rejected because it
  will grow unwieldy and creates merge conflicts as the TUI work adds collector
  requirements (e.g., CPU process stats).
- **ADR:** —

### Choice: MetricValue wrapping scope
- **Chosen:** Wrap all nontrivial typed fields in `MetricValue[T]`; leave primitive
  scalars (uptime, hostname) as plain types where they are always available.
- **Rationale:** Avoids over-engineering host identity fields that are always
  readable, while capturing availability semantics where they matter (NPU, battery,
  devfreq).
- **Alternatives rejected:** Wrap everything — excessive ceremony for guaranteed fields.
- **ADR:** [ADR-004](../adr/ADR-004-metric-availability-states.md)

### Choice: Web API backward compatibility during model migration
- **Options to resolve before M0 is marked complete:**
  - Option A: Keep the web API returning plain dicts (serialize `MetricValue` to
    its inner `value` for the existing JSON shape); TUI uses typed models.
  - Option B: Change the web API to expose `MetricValue` state fields; update
    the dashboard JS to handle the new shape.
  - Option C: Provide both a legacy and a typed API endpoint.
- **Decision:** _Record here when resolved._
- **ADR:** —

### Choice: Fixture directory format
- **Chosen:** Persistent filesystem trees under `tests/fixtures/<scenario>/`
  mirroring `/proc` and `/sys` paths, written once and checked into git.
- **Rationale:** Deterministic, diff-able, reviewable, no generation step on
  each test run, directly usable with `--root tests/fixtures/<scenario>`.
- **Alternatives rejected:** Generate fixtures programmatically in conftest —
  rejected because generative fixtures are harder to inspect and their fidelity
  to real hardware is less auditable.
- **ADR:** —

## Fixture scenarios to create

| Directory | What it covers |
|-----------|----------------|
| `healthy_rk3562/` | Full set: CPU, thermal, network, storage, power, NPU, Rockchip paths |
| `no_npu/` | Generic ARM board: no NPU devfreq, no battery, no Rockchip DT |
| `partial_sysfs/` | Missing cpufreq/devfreq nodes; some thermal zones absent |
| `permission_denied/` | Key paths exist but mode 000 (test the state, not the path) |
| `malformed_metrics/` | Non-numeric values in numeric fields |
| `storage_sd_root/` | Root on mmcblk0 (SD), mmcblk2 (eMMC) also present |
| `storage_emmc_root/` | Root on mmcblk2 (eMMC), no SD block device |
| `battery_absent/` | No `/sys/class/power_supply/` entries |
| `no_network/` | Interfaces present but all operstate=down |

## Acceptance criteria

| Criterion | Status | Notes |
|-----------|--------|-------|
| Web dashboard serves correct snapshot with no behavioral regression | — | |
| `DashboardSampler` can be instantiated without starting the HTTP server | — | |
| All collector functions return typed `MetricValue`-wrapped results | — | |
| `MetricState` enum covers all absence cases present in current collectors | — | |
| Contract tests assert snapshot field shape for web API consumers | — | |
| All fixture scenarios exist and at least one test uses each | — | |
| `ruff check`, `mypy --strict`, `pytest -q` all pass | — | |
| No TUI code contains raw `/proc` or `/sys` path parsing | — | N/A at this milestone |

## Notes

_Record observations, unexpected findings, and deviations from plan here as work
progresses._
