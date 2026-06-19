# ADR-003: RAM-only bounded history; no periodic disk writes

**Status:** Accepted  
**Date:** 2026-06-18  
**Milestone:** M0

## Context

The dashboard needs short-term metric history for sparklines and trend display.
The target device (`samwise`) runs its root filesystem from a microSD card, which
has a finite write-endurance budget. Minimizing writes to the SD card is an
explicit operational constraint.

## Decision

All metric history is held in a fixed-size in-memory ring buffer. No history is
written to disk periodically, no SQLite database is used, no log rotation occurs
during normal operation. History is lost on process restart. The buffer size is
bounded at startup and does not grow.

The only permitted disk write during normal operation is an explicit user-requested
export (`--json` flag or future snapshot-export feature), which is a one-shot
operation, not a background activity.

## Alternatives considered

**Option A — SQLite for persistent history**
Write each sample to an SQLite database for long-term trending.
- Rejected: SQLite performs periodic WAL checkpoints and journal writes; even with
  `PRAGMA journal_mode=WAL` and careful configuration this creates background disk
  I/O incompatible with the SD-card write-reduction posture. Would also add a
  dependency not needed for the short-window sparklines the UI requires.

**Option B — Append-only log file**
Write samples as JSON lines to a rotating log file.
- Rejected: generates continuous writes at the collection cadence (every 2 seconds
  → ~1.7 MB/hour at one line per sample); unacceptable for a microSD root.

**Option C — tmpfs-backed file**
Write history to `/run` (tmpfs) to avoid flash writes.
- Rejected: adds operational complexity (path management, permissions, cleanup on
  crash), provides no durability benefit over in-memory storage, and the
  implementation benefit over a Python `deque` is negligible.

**Option D — Chosen: in-memory ring buffer**
- Accepted: zero writes, zero dependencies, bounded memory, simple implementation,
  semantically correct for a local live-view dashboard that does not need
  persistent trending.

## Consequences

- `sampler.py` owns the ring buffer (`collections.deque(maxlen=N)`).
- History is lost on restart. This is documented and accepted.
- The current `DashboardServer` already uses this pattern; extracting it to a
  standalone sampler preserves the property.
- Sparklines show only the window of samples collected since the process started,
  which may be shorter than the display window on first launch. The UI must handle
  a partially filled history without rendering garbage.
- The `HistoryPoint` model must be documented as RAM-only; no code path should
  attempt to persist it.
