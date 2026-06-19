# Milestone 2: Operational overview screen

**Status:** Not started  
**Git tag:** `milestone/M2-overview` (created on completion)  
**Completed:** —

## Objective

Deliver immediate daily operational value on `samwise`. The overview screen must
give a trustworthy single-screen readout of system health without requiring
navigation to detail pages.

## Deliverables

- [ ] Overview screen with all required panels (see panel list below)
- [ ] Structured unavailable/stale/untrusted display states in all panels
- [ ] Compact layout mode (80×24 to 99×29 terminal range)
- [ ] Sparklines from ring-buffer history (CPU, memory, max temperature, writes)
- [ ] Status bar: refresh rate, pause state, timestamp, compact indicator, key hint
- [ ] Widget library: `panel.py`, `gauge.py`, `sparkline.py`, `status.py`
- [ ] Tests: overview rendering from fixture snapshots, unavailable states,
      compact mode, sparkline with partial history

## Required overview panels

| Panel | Contents |
|-------|----------|
| Host | Hostname, model, kernel, uptime, load averages |
| CPU | Aggregate usage gauge, frequency summary, per-core context |
| Memory | Used/total, usage percent, swap summary |
| Thermal | Maximum temperature, top zone names and values |
| Root storage | Root device, filesystem type, capacity usage |
| SD/eMMC writes | Write rates and cumulative totals, visually distinct |
| Network | Primary interface, RX/TX rates |
| Battery/power | Capacity %, status, charger; "unsupported" if absent |
| NPU | State, frequency, trust indicator; never shown as live gauge if untrusted |
| Top processes | Top-5 by CPU or RSS (configured sort) |

## Implementation choices

### Choice: Sparkline character set
- **Chosen:** UTF-8 block elements (`▁▂▃▄▅▆▇█`) by default; ASCII fallback
  (`_.:!|`) when `--ascii` is set or terminal reports no Unicode support.
- **Missing data:** Render `—` (en dash) for gaps, not `0` or a blank.
  Do not interpolate across missing intervals.
- **ADR:** —

### Choice: SD vs eMMC write panel visual distinction
- **Chosen:** Two side-by-side sub-gauges with distinct labels ("SD" and "eMMC")
  and a combined cumulative total line. In compact mode, collapse to a single
  row with abbreviated labels.
- **Rationale:** The SD write-reduction work is the primary operational concern
  on `samwise`; the distinction must be visually obvious at a glance.
- **ADR:** —

### Choice: NPU trust state rendering
- **Chosen:** If `MetricState` is `STATIC_OR_UNTRUSTED`, render the frequency
  and governor normally but replace the load percentage with a "?" symbol and
  a "(unverified)" label. Never render a gauge bar for untrusted load.
- **Rationale:** A gauge that shows "42%" when the value is static since boot
  is actively misleading; this is the single most important data quality concern
  for the NPU panel.
- **Alternatives rejected:** Hide the NPU panel entirely when untrusted — rejected
  because frequency and governor information is still useful even when load is not.
- **ADR:** [ADR-004](../adr/ADR-004-metric-availability-states.md)

### Choice: Primary interface selection for network panel
- **Chosen:** Prefer the first interface that is `operstate=up` and is not `lo`
  or a virtual interface (detected by absence of `/sys/class/net/<name>/device`).
  If no interface is up, show "no active interface" rather than hiding the panel.
- **ADR:** —

### Choice: Stale data policy
- **Chosen:** Retain last good value for up to 3 missed collection intervals.
  Show age and a "stale" marker. After 3 missed intervals, render `UNAVAILABLE`.
- **ADR:** [ADR-004](../adr/ADR-004-metric-availability-states.md)

## Acceptance criteria

| Criterion | Status | Notes |
|-----------|--------|-------|
| Overview gives a trustworthy operational readout on `samwise` over SSH | — | |
| NPU fields never appear as a live percentage when state is untrusted | — | |
| Battery panel shows "unsupported" cleanly when no power supply exists | — | |
| Missing panels (e.g., no NPU) do not shift or corrupt adjacent panels | — | |
| Sparklines render correctly with a partially filled history buffer | — | |
| Compact mode fits all essential info in 80×24 without truncation artifacts | — | |
| SD and eMMC write totals are visually distinct and correctly attributed | — | |
| Fixture-based rendering tests cover: healthy, no_npu, battery_absent, no_network | — | |

## Notes

_Record observations, unexpected findings, and deviations from plan here._

_Key open question: which thermal zone names should be elevated on the overview
(SOC, CPU, GPU?) vs. shown only in the thermal detail page — resolve by inspecting
actual `samwise` zone names._
