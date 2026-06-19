# ADR-002: TUI_Monster (pyTuiMonster) as the terminal runtime abstraction

**Status:** Accepted  
**Date:** 2026-06-18  
**Milestone:** M1

## Context

The TUI application needs a terminal rendering runtime. Choices range from raw
`curses` to a full third-party TUI framework. The runtime must be suitable for a
constrained Rockchip tablet with minimal dependencies.

## Decision

Use `pyTuiMonster` (the local `TUI_Monster` repository) as the lifecycle, input
routing, and rendering abstraction layer. All direct `curses` API calls stay inside
`pyTuiMonster` and the `rk-tui` widgets; no `curses` import appears in screens or
application-level business logic.

The integration boundary is `rk3562deb_dashboard/tui/app.py`. If `pyTuiMonster`'s
API needs to change to support `rk-tui` requirements, those changes belong in
`TUI_Monster`, not in workarounds scattered through the dashboard code.

## Alternatives considered

**Option A — Raw curses**
Write directly against `curses` with no intermediate layer.
- Rejected: requires reimplementing resize safety, input draining, Unicode-width
  truncation, lifecycle hooks, and the decorator-based key-binding registry —
  all of which `pyTuiMonster` already provides and tests.

**Option B — Textual (Textualize)**
A modern async TUI framework with a rich widget library.
- Rejected: asyncio runtime would be a significant architectural change to the
  existing synchronous dashboard; Textual is a heavy dependency unsuitable for
  a minimal Debian embedded image; and the project's goal is a lightweight
  Rockchip-aware dashboard, not a general-purpose widget toolkit.

**Option C — urwid**
A mature Python curses abstraction with a widget model.
- Rejected: an additional third-party dependency; its widget model is designed
  around its own event loop rather than the project's update/draw cadence; and
  `pyTuiMonster` is already available in-repository and tailored to this project.

**Option D — Chosen: pyTuiMonster**
- Accepted: already available, already tested, lifecycle-hook and decorator-key
  model fits the dashboard's update/draw pattern, `addstr` bounds checking and
  Unicode-width handling are already implemented, and the fake-screen test
  pattern is established.

## Consequences

- `pyTuiMonster` must be added as an optional dependency in `rk3562deb_dashboard`'s
  `pyproject.toml` (e.g., `.[tui]`).
- The version of `pyTuiMonster` in use must be pinned after the initial integration
  stabilizes, because its API is not yet stable (v0.1.0).
- `RKDashboardTui` subclasses `TuiMonsterApp`; it must not bypass the runtime's
  abstractions by calling `curses` directly in application code.
- If `pyTuiMonster` lacks a capability needed by `rk-tui` (e.g., `KEY_RESIZE`
  routing, color pair helpers), the capability should be added to `pyTuiMonster`
  rather than worked around in the dashboard.
