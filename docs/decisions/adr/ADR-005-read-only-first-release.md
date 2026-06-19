# ADR-005: Read-only monitoring in version 1.0; no system mutation

**Status:** Accepted  
**Date:** 2026-06-18  
**Milestone:** M3

## Context

A terminal dashboard that can kill processes, change CPU governors, remount
filesystems, or adjust NPU frequencies is more powerful but also riskier to
run under a normal user account, harder to audit, and more complex to test safely.

## Decision

Version 1.0 of `rk-tui` is strictly read-only. No process signals, no `renice`,
no governor changes, no mount actions, no partition actions, no NPU frequency
overrides. The process screen shows a selected row but provides no action keys.

## Alternatives considered

**Option A — Include process kill/signal gated by --allow-actions flag**
Provide kill/renice in v1.0 but require an explicit CLI opt-in.
- Rejected: adds test burden (must test both modes), requires privilege
  validation, and introduces risk for the primary monitoring use case where
  accidental keypresses near `k` could terminate a critical process. The
  benefit is low compared to `kill`/`renice` already available in the same
  SSH session.

**Option B — Read-only with a future --allow-actions path**
Design the key binding and screen architecture so actions can be added later
without restructuring, but ship no actions in v1.0.
- Accepted variant: the keymap and screen structure should not preclude future
  actions (e.g., reserve `k` on the process screen for "kill" in a future
  release), but no action handlers are implemented now.

## Consequences

- The process screen shows selection state but `Enter` and action keys produce
  no effect or a brief "read-only mode" hint.
- Help overlay must accurately document that the tool is monitoring-only.
- Future `--allow-actions` work is tracked as a deferred feature (spec §4.3).
- Testing is simpler: no need to mock process signaling or governor writes.
