# Decision Records

This directory records the architectural and implementation choices made during the
`rk-tui` project so that git history can serve as a rewind point for any significant
decision.

## Structure

```
decisions/
  README.md          — this file
  adr/               — Architectural Decision Records (cross-cutting, long-lived)
  milestones/        — Per-milestone choice logs (implementation-level, chronological)
```

## How to use this

**Finding a decision:** Browse `adr/` for cross-cutting architectural choices or
`milestones/` for choices made during a specific milestone.

**Rewinding to a milestone:** Each completed milestone is tagged in git.
Check out the tag to see the exact codebase state plus the decision files
that were current at that point:

```
git tag --list 'milestone/*'
git checkout milestone/M0-baseline
```

**Adding a record:** When a meaningful choice is made during implementation —
especially when an alternative was seriously considered and rejected — record it.
Either add a new ADR or add a "Choice" block to the active milestone file.

## ADR status values

| Status | Meaning |
|--------|---------|
| `Proposed` | Under consideration; not yet implemented |
| `Accepted` | Implemented and in effect |
| `Superseded` | Replaced by a later ADR (link provided) |
| `Rejected` | Considered but not adopted |

## Milestone status values

| Status | Meaning |
|--------|---------|
| `Not started` | Work has not begun |
| `In progress` | Active development |
| `Complete` | All acceptance criteria met; milestone tag created |
