# ADR-006: TUI operates locally; no HTTP server dependency

**Status:** Accepted  
**Date:** 2026-06-18  
**Milestone:** M1

## Context

The `rk-tui` application needs to source its metrics from somewhere. One option
is to reuse the existing HTTP API exposed by `rk-dashboard`. Another is to
collect directly from `/proc` and `/sys` in-process.

## Decision

`rk-tui` collects metrics directly in-process via the shared sampler. It does not
require `rk-dashboard` to be running and makes no network connections during
normal operation.

## Alternatives considered

**Option A — TUI as HTTP client consuming /api/snapshot**
On each refresh, the TUI fetches `http://localhost:8765/api/snapshot`.
- Rejected:
  1. The TUI cannot start if `rk-dashboard` is not running — defeats the purpose
     of a standalone console diagnostic tool.
  2. Adds a network round-trip on every refresh cycle.
  3. Introduces snapshot age ambiguity (HTTP response may be from the last server
     sample, not a fresh collection).
  4. Does not work on serial consoles or when the network is down.
  5. Unnecessarily exposes a local HTTP port.

**Option B — Chosen: in-process direct collection**
`rk-tui` instantiates `DashboardSampler` directly and calls `sample()` on each
refresh interval.
- Accepted: no network, no service dependency, same data quality as the web UI,
  works on serial console, works with network down, works without root.

## Consequences

- `DashboardServer` and `DashboardSampler` must be decoupled so the sampler
  can be instantiated without starting the HTTP server. This is required work
  for Milestone 0.
- The TUI and web server can run simultaneously, each with their own sampler
  instance and collection interval. This is documented behavior, not a bug.
- A future "remote TUI mode" that consumes a secured HTTP or WebSocket endpoint
  is a deferred feature (spec §4.3) and is explicitly not part of v1.0.
