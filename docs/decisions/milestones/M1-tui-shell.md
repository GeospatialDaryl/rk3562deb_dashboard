# Milestone 1: TUI runtime integration and smoke application

**Status:** Not started  
**Git tag:** `milestone/M1-tui-shell` (created on completion)  
**Completed:** —

## Objective

Establish `rk-tui` as an installable, safe, resize-aware terminal application that
can render a minimal screen from fixture snapshots and exit cleanly under all
expected termination scenarios.

## Deliverables

- [ ] Add `pyTuiMonster` as optional `[tui]` dependency in `pyproject.toml`
- [ ] Add `rk-tui` console entry point (`rk3562deb_dashboard.tui.main:main`)
- [ ] Create `rk3562deb_dashboard/tui/` subpackage (main, app, state, layout, formatting)
- [ ] Implement `RKDashboardTui(TuiMonsterApp)` application shell
- [ ] Implement `TuiState` dataclass
- [ ] Implement minimum terminal size guard (< 80×24 → safe message, no crash)
- [ ] Implement resize detection and reflow
- [ ] Implement global key bindings: `q`/`Q`/Ctrl-C exit, `?`/`h` help overlay,
      `p` pause, `r` refresh, `1`–`7` screen switch, Tab/Shift-Tab navigation, Esc
- [ ] Implement help overlay modal
- [ ] Render a minimal host/CPU/memory screen from a fixture snapshot (`--once`)
- [ ] Create fake-screen test harness (`tests/tui/fake_screen.py`)
- [ ] Add tests: layout breakpoints, minimum-size guard, keymap, help modal

## Implementation choices

### Choice: pyTuiMonster installation method
- **Options to resolve:**
  - Option A: Local path dependency (`"pyTuiMonster @ file:///home/frodo/repos/TUI_Monster"`)
  - Option B: Git URL dependency (`"pyTuiMonster @ git+https://github.com/..."`)
  - Option C: Copy `pyTuiMonster/` into this repo (vendor)
  - Option D: Publish `pyTuiMonster` to PyPI and use a version specifier
- **Decision:** _Record here when resolved._
- **ADR:** [ADR-002](../adr/ADR-002-tui-monster-runtime.md)

### Choice: Fake screen harness location
- **Chosen:** `tests/tui/fake_screen.py` — a new harness maintained in
  `rk3562deb_dashboard`, modelled on the pattern in `TUI_Monster/tests/test_runtime.py`
  but adapted to track panel-level draw calls and out-of-bounds attempts as errors.
- **Rationale:** The `TUI_Monster` `FakeScreen` is in a test file, not exported
  as a library artifact. Rather than importing from another project's test module,
  we own our test harness and extend it as needed for dashboard-specific assertions.
- **Alternatives rejected:** Import `FakeScreen` directly from TUI_Monster tests —
  rejected because test modules are not a stable public API and the import path
  would break if TUI_Monster reorganizes its tests.
- **ADR:** —

### Choice: Metric collection cadence vs. render cadence
- **Chosen:** Two separate intervals. `TuiConfig.refresh_rate` controls the curses
  input/render loop cadence (default ~30ms for responsive keypresses). The sampler
  collects at the configured `--interval` (default 2.0s). The `update()` method
  checks elapsed time and calls `sampler.sample()` only when the collection
  interval has elapsed.
- **Rationale:** A 2-second render loop would make keypresses feel sluggish.
  A 30ms collection loop would be CPU-wasteful and inaccurate for rate calculations.
- **ADR:** —

### Choice: KEY_RESIZE handling
- **Options to resolve:**
  - Option A: Check `curses.KEY_RESIZE` in `_process_input` inside TUI_Monster;
    route to an `on_resize()` hook.
  - Option B: Check `KEY_RESIZE` in `RKDashboardTui.draw()` via `screen.getmaxyx()`
    comparison on each frame; reflow when dimensions change.
  - Option C: Add resize routing to `TuiMonsterApp` as a new lifecycle hook.
- **Decision:** _Record here when resolved. Preferred: Option C, adding to TUI_Monster._
- **ADR:** —

## Acceptance criteria

| Criterion | Status | Notes |
|-----------|--------|-------|
| `rk-tui --root tests/fixtures/healthy_rk3562 --once` exits 0 | — | |
| `q`, `Q`, and Ctrl-C restore the terminal correctly | — | |
| Terminal < 80×24 shows a safe message; no crash, no garbled output | — | |
| Resize from wide to narrow reflowing without restart | — | |
| Help overlay appears on `?` and closes on `?` or Esc | — | |
| Fake-screen tests cover all four layout size breakpoints | — | |
| `ruff`, `mypy`, `pytest` pass | — | |

## Notes

_Record observations, unexpected findings, and deviations from plan here._
