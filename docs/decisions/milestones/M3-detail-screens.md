# Milestone 3: Detail screens

**Status:** Not started  
**Git tag:** `milestone/M3-detail-screens` (created on completion)  
**Completed:** —

## Objective

Provide diagnostic depth across all seven screens. Each screen must be fully
navigable via keyboard, fixture-tested, and safe at constrained terminal sizes.
No system mutation actions are present in this release.

## Deliverables

- [ ] Screen 2 — CPU: per-core gauges, frequencies, load averages, history sparklines
- [ ] Screen 3 — Storage: root device, mounts, device classification, write totals,
      SD/eMMC summary, partition identity
- [ ] Screen 4 — Network: interface list with state/rates/counters, interface selection,
      Wi-Fi state where readable, sparkline for selected interface
- [ ] Screen 5 — Thermal/Power: all thermal zones with severity markers, max-temp
      history, battery detail, charger state
- [ ] Screen 6 — NPU/Rockchip: board identity, NPU clock/governor/trust warning,
      GPU/media/RGA presence, devfreq summary, storage bus identity
- [ ] Screen 7 — Processes: top-N table, sort cycling (`s`), row selection
      (arrow/`j`/`k`), read-only detail pane, process count summary
- [ ] Widget additions: `table.py`, `modal.py` (detail pane), scrollable list
- [ ] Tests: each screen fixture-tested for normal, unavailable, and narrow-terminal
- [ ] `1`–`7` direct navigation confirmed stable

## Implementation choices

### Choice: Storage device classification
- **Chosen:** Classify by reading `/sys/block/<dev>/device/type` (SD/MMC),
  checking for `nvme` prefix, and falling back to "unknown". The root device
  is identified by cross-referencing `/proc/self/mountinfo`.
- **Rockchip/Android partition layout:** Surface partition table size and count
  where readable from `/sys/block/<dev>/`, but do not assume a specific partition
  naming scheme.
- **ADR:** —

### Choice: Process CPU tracking
- **Current gap:** `collect_processes` currently only ranks by RSS; top-by-CPU
  requires `/proc/<pid>/stat` delta tracking.
- **Chosen:** Add CPU time delta tracking to `ProcessCollector` in the
  `collectors/process.py` refactor (this was deferred from M0 if not done then).
- **Alternatives rejected:** Show only RSS sort in v1.0 — rejected because the
  spec explicitly requires sort by CPU, and it is needed for meaningful process
  monitoring.
- **ADR:** —

### Choice: Network interface Wi-Fi state
- **Chosen:** Read wireless state from `/proc/net/wireless` and link quality
  from `/sys/class/net/<iface>/wireless/` where available. Do not depend on
  `iwconfig`, `iw`, or any external binary. Show "Wi-Fi: no data" if the
  kernel interface is absent rather than hiding the row.
- **ADR:** —

### Choice: NPU trust warning prominence
- **Chosen:** When NPU load state is `STATIC_OR_UNTRUSTED`, render a yellow/
  attention-colored banner at the top of the NPU/Rockchip screen:
  "NPU load value may not reflect live utilization — frequency and governor only."
- **Rationale:** The spec is explicit that this must be prominent; a footnote
  is insufficient.
- **ADR:** [ADR-004](../adr/ADR-004-metric-availability-states.md)

### Choice: Process detail pane behavior
- **Chosen:** Selecting a process row with `Enter` shows a right-side or
  bottom pane with PID, name, state, RSS, and command line (truncated).
  No action buttons. Pressing `Enter` again or `Esc` closes the pane.
- **Alternatives rejected:** Full-screen process detail — rejected as
  disproportionate to a read-only display; a split pane preserves context.
- **ADR:** [ADR-005](../adr/ADR-005-read-only-first-release.md)

### Choice: Command-line display in process table
- **Chosen:** Truncate to available column width. Do not implement redaction
  of secret patterns in v1.0 — the spec defers this to open question §24.6.
  Record the decision here when resolved.
- **Decision:** _Record here._
- **ADR:** —

## Acceptance criteria

| Criterion | Status | Notes |
|-----------|--------|-------|
| Direct navigation via `1`–`7` is consistent and instant | — | |
| Each screen renders without error under `no_npu`, `no_network`, `battery_absent` fixtures | — | |
| Each screen renders a compact or truncated form at 80×24 | — | |
| Process sort cycles through CPU/RSS/PID/name with visible header update | — | |
| Storage screen clearly labels SD vs eMMC write totals | — | |
| NPU screen shows trust warning banner when state is STATIC_OR_UNTRUSTED | — | |
| No process or system mutation action is present anywhere in the UI | — | |
| All new screens have fake-screen rendering tests | — | |

## Notes

_Record observations, unexpected findings, and deviations from plan here._

_Key open question: which GPU/media/RGA devfreq paths are present on `samwise`?
Inspect `samwise` before finalizing the NPU/Rockchip screen layout._
