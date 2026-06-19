# ADR-004: Explicit metric availability and trust states

**Status:** Accepted  
**Date:** 2026-06-18  
**Milestone:** M0

## Context

Rockchip hardware telemetry is variable: sysfs paths may be absent on some
kernels, NPU load values may be static rather than live, battery interfaces are
absent on non-tablet boards, and counters can reset. The UI must communicate this
faithfully rather than silently showing zero or omitting the field.

A plain Python `None` is insufficient because it conveys only "absent" and loses
why the value is absent.

## Decision

Every non-trivial metric exposed to the UI is wrapped in a `MetricValue[T]`
container that carries an explicit `MetricState` enum value, an optional human-
readable `detail` string, an optional `source` path for diagnostics, and an
optional `captured_at` timestamp for staleness tracking.

```python
class MetricState(StrEnum):
    AVAILABLE          = "available"
    UNAVAILABLE        = "unavailable"       # expected but temporarily absent
    UNSUPPORTED        = "unsupported"       # hardware/kernel does not expose this
    PERMISSION_DENIED  = "permission_denied" # path exists but not readable
    MALFORMED          = "malformed"         # data present but unparseable
    STALE              = "stale"             # last known good value, age shown
    STATIC_OR_UNTRUSTED = "static_or_untrusted"  # value may not reflect live state
```

The UI renders each state with a distinct visual treatment; it never silently
displays STATIC_OR_UNTRUSTED data as if it were live.

## Alternatives considered

**Option A — Plain Optional[T] / None**
Return `None` for missing values and let the UI interpret absence.
- Rejected: loses the reason for absence; cannot distinguish "NPU not present"
  from "NPU path temporarily unreadable" from "NPU load is static"; makes it
  impossible to render appropriate user-facing explanations.

**Option B — Boolean flag alongside value**
Add an `is_available: bool` field next to each metric.
- Rejected: boolean cannot express the STALE, PERMISSION_DENIED, MALFORMED, or
  STATIC_OR_UNTRUSTED distinctions that matter for correct UI rendering.

**Option C — Exception-based signaling**
Raise typed exceptions from collectors and catch them in the UI.
- Rejected: exceptions as control flow are expensive per-sample and make the
  data model harder to test and serialize; the sampler would need try/except
  at every field access site.

**Option D — Chosen: MetricValue[T] with MetricState enum**
- Accepted: explicit, typed, testable, serializable, extensible; the state enum
  can gain new values without breaking existing rendering code that handles the
  unknown case; matches how availability information is described throughout the
  spec.

## Consequences

- `models.py` and `availability.py` must be implemented before any TUI code.
- Existing `collectors.py` functions return plain dicts; they must be updated to
  return `MetricValue`-wrapped typed models as part of Milestone 0.
- The web API JSON output will change shape when typed models replace plain dicts.
  The existing web dashboard JS will need updating or a compatibility shim if the
  serialization format changes. This must be resolved before merging M0.
- Tests must cover the availability state transitions, not just the happy path.
- `STATIC_OR_UNTRUSTED` is specifically reserved for the NPU load field on
  kernels where the value does not change under load. The UI must never show
  this as a live gauge percentage.
