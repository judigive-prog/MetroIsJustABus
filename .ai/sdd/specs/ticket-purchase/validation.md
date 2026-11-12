# Validation — Ticket Purchase

## Scope and traceability

Selected complete scenario: **AS-01, happy path.** An authenticated passenger buys an active ticket type (150 c, EUR) with a new idempotency key and token `sim_approve`. Expected: `201 COMPLETED` with a `ticketId`; one purchase, one ticket with the snapshot terms, one `ISSUED` state change, one pending `TicketPurchased` outbox event, one charge at `payment-sim`.

**Status: implemented, not validated.** No executable tests were written or run in this session, so AS-01 is **not** demonstrated. By the PL7 definition, the scenario is not complete until the tests below exist and pass.

| Requirement / scenario | Task | Code location | Test identifier | Final result |
| --- | --- | --- | --- | --- |
| PUR-FR-02, AS-01 | T-08, T-09 | `apps/ticketing-service/purchases/services.py` `create_purchase`; `purchases/api/views.py` `PurchaseCreateView` | — | Not run (no test) |
| PUR-FR-03, AS-14 | T-09 | `purchases/api/views.py` `_idempotency_key` | — | Not run (no test) |
| PUR-FR-04, PUR-FR-05 | T-08 | `services.py` `_resolve_existing`, `uq_purchases_passenger_key` | — | Not run (no test) |
| PUR-FR-06, PUR-FR-17 | T-04, T-08 | `purchases/models.py` snapshot fields; `finalize_approved` copies the snapshot | — | Not run (no test) |
| PUR-FR-07, PUR-FR-16 | T-08 | `services.py` `_purchasable_ticket_type` | — | Not run (no test) |
| PUR-FR-08 | T-07 | `purchases/clients.py` `HttpPaymentClient.pay` | — | Not run (no test) |
| PUR-FR-09, AS-01 | T-08 | `services.py` `finalize_approved` (one transaction: ticket, state change, COMPLETED, outbox) | — | Not run (no test) |
| PUR-FR-10 | T-08 | `services.py` `finalize_declined` | — | Not run (no test) |
| PUR-FR-11 | T-07, T-08 | `clients.py` maps errors to `UNCERTAIN`; `services.py` `_schedule_retry` | — | Not run (no test) |
| PUR-FR-13, PUR-FR-14 | T-02, T-09 | `common/auth.py`, `common/permissions.py`, `PurchaseDetailView` | — | Not run (no test) |
| PUR-FR-15 | T-05 | `outbox/services.py` `enqueue`; `packages/metro_common/metro_common/events/ticket_purchased.py` | — | Not run (no test) |
| PUR-FR-01 | T-09 | `ticket_types/api/views.py` `TicketTypeListView` | — | Not run (no test) |
| D-05, D-11 (sim) | T-06 | `simulators/payment-sim/payments/services.py` | — | Not run (no test) |

Not implemented in this slice: reconciler (T-10, blocked by OQ-02), outbox relay (T-05 relay part), JWKS fetching with a cache (N-13), database-level UPDATE/DELETE block on `ticket_state_changes` (T-04), contract files and drift checks (T-11), Dockerfiles and compose entries, migrations.

## Execution evidence

Working directory: repository root.

- Only check run: `python -I -m compileall -q apps/ticketing-service simulators/payment-sim packages/metro_common`
  Result: no syntax errors. This proves nothing about behaviour; no dependencies were installed and Django was never started.
- Initial failing baseline: **not established.** No tests exist. PostgreSQL is needed for the integration tests and Docker is not installed on the machine used.
- Final test run: **none.**

Commands to set up and reach AS-01 manually (not executed):

```bash
cd apps/ticketing-service && uv sync
uv run python manage.py makemigrations common outbox ticket_types tickets purchases
uv run python manage.py migrate
uv run python manage.py seed_ticket_types
```

Each needs the variables from `.env.example` and a running PostgreSQL. `payment-sim` is set up the same way (`makemigrations payments`, `migrate`) with its own `.env.example`.

## Specification gaps found while implementing

These are design issues found in the code, not decided by the team. Each needs a team decision.

| # | Finding | What the code does now |
|---|---|---|
| 1 | Design §3 does not store the payment token, but the reconciler must replay the payment with the same payload, and payment-sim compares the token (design §5.2). Without it, a replay gets 409 | Added `purchases.payment_method_token` (simulated opaque token, never logged or returned) |
| 2 | Design §5.2: `sim_error` "records nothing" on the first call but returns APPROVED on later calls. The sim cannot know a call is "later" without recording it | Records an `ERRORED` payment with no charge; the next call approves it |
| 3 | `sim_lose_response` (record, then drop the connection) cannot be done from a Django view | Returns 501 and records nothing. AS-07 cannot be exercised yet |
| 4 | Design §6.1 says "4xx other than the 409 contract error" without saying what a 409 from payment-sim means for the purchase | Treated as `UNCERTAIN` and logged as `payment_idempotency_conflict` |
| 5 | PUR-NFR-13 requires a format check on `paymentMethodToken`, but no format is specified | Placeholder: `^[A-Za-z0-9_]{1,64}$` |
| 6 | OQ-01, OQ-02, OQ-03 are still open (marked blocking in requirements §7) | Code follows the design's proposals: 202 for uncertain outcomes, payment-sim at `/api/payment-sim/v1/payments` with SQLite storage. No reconciler |
| 7 | JWT claim names (`sub`, `role`) are an assumption (design §10) | Implemented as assumed; public key read from a file |

## AI assistance and human decisions

- Tool/model and representative instruction(s): *to be completed by the team*
- Human review and significant decision(s): *to be completed by the team. The code has not been reviewed yet.*
- Artifact refinements: none made to requirements.md, design.md or tasks.md; the gaps above are listed for the team to decide

## Limitations and reflection

AS-01 is coded but unproven: there is no failing baseline, no passing test and no human review, so nothing here meets the PL7 completion bar yet. Next steps: install Docker, write the AS-01 integration test (real PostgreSQL, payment-sim stub or container, assert the five row counts), run it, then review the code.

*Reflection: to be written by the team.*
