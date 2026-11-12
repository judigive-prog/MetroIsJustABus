# Ticket Validation — Tasks

**Status:** initial breakdown for PL7 (PL6, 2026-10-27). Based on [requirements.md](requirements.md) and [design.md](design.md). Do not start until the team has confirmed the *proposed* decisions D-02 to D-09, or updated the tasks.

Every commit carries `Req:` with the TV-REQ ids it covers (conventions). Tests carry `@pytest.mark.req(...)` with the matching FR id.

## Prerequisites (outside this feature)

The repository has no application code yet. These belong to the milestone 2 skeleton; this feature needs them.

| ID | Task | Area | Done when |
|---|---|---|---|
| TV-P01 | `ticketing-service` Django project with settings, health endpoints, error handler, correlation-id middleware, injectable clock | `apps/ticketing-service/` | Service starts in Docker; `/health/ready` returns 200; a test can freeze the clock |
| TV-P02 | `outbox_event` model and the outbox write helper (relay not required) | `apps/ticketing-service/events/` | Helper inserts an event inside a caller's transaction; unit test passes |
| TV-P03 | `tickets` model with `terms`, `status`, `remaining_journeys`, `activated_at`, `valid_until`, `version` (may be shared with the purchase feature) | `apps/ticketing-service/` | Migration applies; check constraint rejects negative journeys |

## Implementation tasks

| ID | Task | Req | Area | Depends on | Done when |
|---|---|---|---|---|---|
| TV-T01 | Add `validators`, `validation_attempts` and `ticket_state_changes` models and migrations with the named unique and check constraints; make the two history tables append-only | 04, 06, 08 | `models.py`, migrations | P01, P03 | Migration applies on a clean database; inserting a duplicate (validator, key) fails with the named constraint |
| TV-T02 | Write the pure rule evaluator `evaluate(terms, ticket_state, now) -> Decision` implementing the order in design §4 step 5 | 02, 03, 05, 11 | `services.py` (or `domain/`) | — | Unit tests TV-V01 pass with no database |
| TV-T03 | Write `validate_ticket(validator, ticket_id, device_time, key)` in `services.py`: lock, idempotency lookup, evaluate, update ticket, append state changes, insert attempt, write outbox event, all in one transaction; replay on unique violation | 04 to 09, 11 | `services.py` | T01, T02, P02 | Integration tests TV-V02 to TV-V04 pass |
| TV-T04 | Add validator authentication and permission class: accept only the `validator` service role and an `ACTIVE` validator; resolve the stop server-side | 10 | `api/permissions.py` | P01 | API tests TV-V05 pass. Uses a test token signed with the dev key; **production credential issuing is blocked by OQ-03** |
| TV-T05 | Add `POST /api/ticketing/v1/validations`: request and response serializers, `Idempotency-Key` required, drf-spectacular schema, mapping of 409 and 503 | 01, 06 | `api/` | T03, T04 | API tests pass; committed OpenAPI file matches the generated one |
| TV-T06 | Define `TicketValidated` v1 event model and JSON Schema; build the payload without ticket or passenger ids | 09 | `packages/metro_common`, `contracts/events/` | P02 | Schema test TV-V06 passes |
| TV-T07 | Add seed fixtures: two validators at different stops, one inactive validator, a 10-journey ticket, a 1-journey ticket, a 24 h pass, a cancelled ticket | all | `apps/ticketing-service/fixtures/` | T01 | `loaddata` succeeds on a clean database; fixtures used by the tests below |
| TV-T08 | Extend `validator-sim` to send a validation (with a fresh or a repeated key) for the demo | 01, 06 | `simulators/validator-sim/` | T05 | Sim prints the result for each seed ticket against the dev stack |

## Validation tasks

| ID | Task | Covers | Depends on | Done when |
|---|---|---|---|---|
| TV-V01 | Unit tests for the evaluator, one per rule and per reason order, with a fixed clock | AC-01 to AC-08, AC-13 | T02 | All pass; `@pytest.mark.unit` |
| TV-V02 | Integration tests (real PostgreSQL via testcontainers) for each acceptance scenario on a fresh database: records, state changes, outbox rows, stored device time next to the server decision time | AC-01 to AC-08, AC-12, AC-13 | T03, T07 | All pass; each asserts row counts, not only the response |
| TV-V03 | Idempotency tests: same request twice → one effect; same key and ticket with a later device time → replay; same key, other ticket → 409; parallel same key on an unknown ticket → one record | AC-09, AC-10, AC-10b | T03 | Pass; required by conventions for every retry-safe operation |
| TV-V04 | Concurrency test: two threads validate a 1-journey ticket at once, repeated 50 times | AC-11 | T03 | Every run gives exactly one ACCEPTED and one REJECTED |
| TV-V05 | API tests for authentication and authorisation: no token, passenger token, inactive validator | AC-14 | T04, T05 | 401 / 403 / 403; no attempt recorded |
| TV-V06 | Event contract test: an accepted validation's outbox payload validates against the committed `TicketValidated` v1 schema and contains no ticket id | REQ-09, D-08 | T03, T06 | Pass; `@pytest.mark.contract` |
| TV-V07 | Failure test: stop PostgreSQL during a request → 503; restart → retry with the same key succeeds once | AC-15 | T05 | Pass; `@pytest.mark.failure` |
| TV-V08 | Mutation testing (mutmut) on the evaluator | REQ-02, 03 | V01 | Surviving mutants reviewed and either killed by new tests or justified in review.md |

## Order

```text
P01 → P03 → T01 → T07
P01 → P02 → T06
T02 → V01 → V08
T01 + T02 + P02 → T03 → V02, V03, V04, V06
P01 → T04
T03 + T04 → T05 → V05, V07 → T08
```

## Blocked or deferred

| Item | Blocked by | What PL7 does instead |
|---|---|---|
| Production validator credentials | OQ-03 | Test tokens signed with the dev key |
| Transfer window, anti-passback | OQ-01, OQ-02 | Implement D-05 (one journey per accepted validation); no task until decided |
| Validator management by staff | OQ-04 | Seed data (T07) |
| Performance check of the 1 s target | OQ-06, NFR-043 load figures | Not in PL7 |
