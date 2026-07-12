# ADR-007: Launcher page as the kiosk home

## Status

Accepted (2026-07-11)

## Context

The appliance's cog kiosk pointed at `/`, which served the metrics dashboard.
App switching (camera-cv, mapping) was a blind `--next` cycle driven by a
touch gesture, with per-app actions scattered between dashboard Controls
buttons and gesture corners. The metrics dashboard was the de-facto center of
the device even though monitoring is only one of its functions.

## Decision

`/` now serves a dedicated launcher page (`static/launcher.html`); the metrics
dashboard moved to `/dashboard`. The launcher is served by this same server —
no new systemd unit, no new polkit rules — and drives the existing
`POST /api/control/<action>` mechanism plus one new read-only endpoint,
`GET /api/launcher-status` (active app, battery, power profile, current CV
demo).

Two deliberate deviations from prior rules:

- `CONTROL_ACTIONS` gains `power-toggle`, which is not a `systemctl` argv.
  It is still a fixed argv with no user input; the underlying profile change
  is authorized by the `51-samwise-power-profile.rules` polkit rule.
- `set-cv-demo` is special-cased before the `CONTROL_ACTIONS` table: it is a
  plain file write of a validated demo name to
  `$XDG_RUNTIME_DIR/cv-demo-current` (the file `cam_detect.py` polls each
  frame), not a subprocess. It requires `ReadWritePaths=-/run/user/1001` in
  the unit because of `ProtectSystem=strict`. The demo allow-list `CV_DEMOS`
  is a literal mirror of `~/src/camera-npu/demos/__init__.py` to avoid a
  cross-repo import.

## Amendment (2026-07-12)

All state-changing POSTs (`/api/control/*` including `set-cv-demo`, and
`/api/wifi/*` writes) are accepted **only from 127.0.0.1**. The 2026-07-12
stability review found the LAN-open control surface allowed any LAN client
to flip the screen owner or start a heavy CV demo (a documented
CPU-starvation vector). The kiosk browser talks to 127.0.0.1 so on-panel
controls are unaffected; the LAN retains the read-only GET surface.

## Consequences

- The kiosk boots into a launch page with direct-select app tiles; the
  gesture bottom-right corner becomes "home" (`app-switch dashboard`) instead
  of `--next` cycling.
- The launcher polls only `/api/launcher-status` (15 s, paused when hidden),
  so an idle home screen is cheaper than the old always-on metrics page.
- `CV_DEMOS` must be kept in sync with camera-npu's `DEMOS` list when demos
  are added.
