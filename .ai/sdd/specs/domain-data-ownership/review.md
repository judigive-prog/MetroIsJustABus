# DES-01 — Review and acceptance evidence

Version: 0.1 draft, 2026-11-10.
Issue: [MET-169](https://linear.app/metroisjustabus-ase/issue/MET-169).
Repository baseline inspected: 1ef7afb3ccb8c4ca5b949b2fbe325c93e0aa14b6.
Status: ready for team review; acceptance and merge pending.

## Acceptance checklist

| MET-169 acceptance criterion | Evidence prepared | Status |
|---|---|---|
| Model all listed business domains | design.md sections 1–5, two ER diagrams and entity tables | Draft prepared |
| Record identifiers, relationships, invariants, lifecycles and authoritative owners | design.md ownership table, per-entity rows, consistency boundaries and lifecycle table | Draft prepared |
| Keep A-01–A-14 visible and provisional | assumptions.md links all fourteen decision tickets and records model consequences | Draft prepared; approvals pending |
| Review consistency with FR/NFR and version accepted model/rationale | design.md traceability table and reconciliation findings; draft version 0.1 | Agent consistency check prepared; human review and accepted version pending |

MET-168 is still the recorded completion prerequisite. Its workflow/ownership
agreement must be evidenced before MET-169 is closed. No ticket status was
changed by this work.

## Consistency findings

- The adopted stack already selects Django and PostgreSQL. MET-169 records
  logical ownership; it does not repeat the technology implementation.
- Purchase models exist in the baseline; validation is preliminary. The
  differences in snapshot/state-change field names are recorded for later
  feature reconciliation rather than silently changing existing models.
- The A-series issues remain open even where steering files present a working
  choice. Entrance validation, occupancy attribution, notification channels
  and retention are explicitly provisional.
- Stable network/schedule/ticket-type data is separated from operational
  state and immutable history. Cross-service relationships are UUID references,
  not database foreign keys.
- This design covers the whole domain only because DES-01 requires that
  coverage; it adds no implementation for the later feature issues.

## Review record

| Reviewer / decision | Date | Result / rationale |
|---|---|---|
| Codex draft consistency review | 2026-11-10 | Matched requested domain coverage and A-01–A-14; identified route/run identity and purchase/validation reconciliation questions |
| Team model and ownership review | Pending | Confirm proposed entities/cardinalities, owners, lifecycle guards and referenced open decisions |
| Accepted model version / approval evidence | Pending | Version the accepted revision after real review; do not infer approval from this draft |

## Scope of this branch

Only this design directory belongs to MET-169. No migrations, runtime models,
API endpoints, fixtures, CI edits or generated API contracts are part of it.
The previously generated implementation was preserved in a named local Git
stash for selective reuse in the appropriate later issues. It is not evidence
of DES-01 acceptance. Local secrets/tools remain excluded through Git's local
exclude file, outside this branch's proposed changes.
