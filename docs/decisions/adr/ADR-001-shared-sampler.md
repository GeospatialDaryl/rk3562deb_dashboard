# ADR-001: Shared in-process sampler for web and TUI

**Status:** Accepted  
**Date:** 2026-06-18  
**Milestone:** M0

## Context

The project needs two user interfaces over the same hardware telemetry: the existing
web dashboard and the new `rk-tui` terminal interface. A decision is needed about
where metric collection lives and how each interface consumes it.

## Decision

`rk-tui` instantiates the same collector and sampler layer used by the web dashboard,
running in the same process. There is no shared daemon. Both interfaces may run
independently; if both run simultaneously each maintains its own sampler instance.

## Alternatives considered

**Option A — TUI as HTTP client of the web dashboard**
The TUI would call `http://localhost:8765/api/snapshot` on each refresh.
- Rejected: introduces a service-coupling dependency (TUI cannot run if the web
  server is not started), adds JSON serialization/deserialization overhead, creates
  ambiguity about snapshot age, and is wrong for a local console or serial terminal.

**Option B — Shared background daemon**
A dedicated collector daemon would serve both interfaces over a socket or shared
memory.
- Rejected: adds significant operational complexity (daemon lifecycle, socket
  permissions, restart behavior) with no measured benefit at this scale. Deferred
  as a future option if duplicate in-process sampling proves to be a measurable
  resource problem on `samwise`.

**Option C — Chosen: in-process shared code, independent instances**
Both interfaces import from the same `collectors` and `sampler` modules. Each
running interface owns one sampler instance.
- Accepted: no network dependency, no daemon, no serialization, simple startup,
  testable with the same fixture-root mechanism already in use.

## Consequences

- `sampler.py` must be extractable from `DashboardServer` so `rk-tui` can
  instantiate it directly without starting the HTTP server.
- If both `rk-dashboard` and `rk-tui` run simultaneously, the system runs two
  independent collection loops. This is acceptable given the low collection overhead.
- Future migration to a shared daemon is still possible; the sampler interface
  becomes the abstraction boundary.
