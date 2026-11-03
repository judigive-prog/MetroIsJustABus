# Tasks — Ticket Purchase with Simulated Payment

**Status:** DRAFT for PL7. Nothing here is implemented in PL6.
Traces use IDs from `requirements.md` (`FR` = `PUR-FR`, `NFR` = `PUR-NFR`, `AS` = acceptance scenario). `Blocked by` names an unresolved item in `requirements.md` §7; a blocked task must not start by silently assuming an answer (principle 11).

Working rules for every task (from conventions.md): branch `feat/ticketing-<short-name>`; Conventional Commit with scope `ticketing` (or `payment-sim`); trailers `Req:` (see OQ-04 for the ID scheme), `Agent:`, `Human-Intervention:`; mypy and ruff clean; tests carry `@pytest.mark.req("<ID>")`; PR lists requirement IDs, verifying tests and changed contract files.

## Execution order

```text
T-00 ─┬─> T-06 ─> T-07 ─┐
      ├─> T-09 (202/503 part)
      └─> T-10 (reconciler role)
T-01, T-02, T-03 ─> T-04 ─> T-08 ─> T-09 ─> T-11
T-05 ─────────────────────> T-08 (event), T-24
T-08 ─> T-20 ─> T-21 ─> T-22 ─> T-23 ─> T-26
T-04..T-10 ─> T-27, T-28, T-29
```

## A. Decisions and foundations

| ID | Task | Area | Traces | Depends | Done when | Blocked by |
|---|---|---|---|---|---|---|
| T-00 | **Team decisions (human).** Resolve OQ-01, OQ-02, OQ-03; confirm D-01..D-13. Update `conventions.md` / `tech-stack.md` or this spec so they no longer conflict. | `.ai/` | all | — | Each OQ marked resolved in `requirements.md` with the chosen option and the document updated; `review.md` records it. | — |
| T-01 | **Populate `AGENTS.md`** (currently empty) with the build/test commands, the steering-file pointers and the rules agents must follow; reconcile `PUR-*` IDs with spec v0.2 (OQ-04). | repo root, `.ai/` | NFR-08 | — | `AGENTS.md` non-empty and references the four steering files; ID mapping table committed. | OQ-04 (mapping part) |
| T-02 | **Authentication and permission classes.** Verify JWTs with a cached JWKS key; `passenger_id` from `sub`; `IsPassenger` permission; default deny. Confirm the real claim names with core-backend. | `ticketing-service/purchases/api` | FR-13, FR-14, AS-15 | T-03 | Unit tests with a locally generated key pair: valid token, expired, wrong signature, missing role (403). Claim names confirmed against core-backend's issued token (assumption [A] in design §10 closed). | OQ-06 (cache TTL), OQ-07 (staff) |
| T-03 | **Platform plumbing, if absent:** correlation-id middleware, single exception handler producing the error shape, injectable `clock`, shared HTTP client wrapper (connect 1 s, read 3 s, correlation header, service token), structlog config with redaction of tokens. | `ticketing-service` + `metro_common` | NFR-03, 04, 05 | — | Unit tests: handler output shape per exception, clock injectable, wrapper times out within the budget against a stalled stub, redaction test proves `paymentMethodToken` and `Authorization` never appear in log output. | — |
| T-05 | **Outbox helper and relay role, if absent:** `outbox_event`, `enqueue()` inside the caller's transaction, relay with `select_for_update(skip_locked=True)`, publisher confirms + mandatory routing, topology declared before publishing. Add `TicketPurchased` Pydantic model to `metro_common`; generate JSON Schema into `contracts/events`. | `ticketing-service`, `packages/metro_common`, `contracts/events` | FR-15, NFR-02, NFR-06 | T-03 | Event contract file generated and committed; integration test (real RabbitMQ) publishes one message and marks it published only after confirmation. | — |

## B. Implementation

| ID | Task | Area | Traces | Depends | Done when | Blocked by |
|---|---|---|---|---|---|---|
| T-04 | **Models and migrations:** `ticket_types`, `tickets`, `ticket_state_changes`, `purchases` with the named constraints in design §3; DB-level block of UPDATE/DELETE on `ticket_state_changes`; seed command/fixture for a few ticket types (EUR). | `ticketing-service/{ticket_types,tickets,purchases}` | FR-02, 06, 09; NFR-01, 07 | T-03 | Migrations apply on a clean PostgreSQL; tests prove each constraint raises (`uq_purchases_passenger_key`, `uq_tickets_purchase`, status checks, terminal-has-response) and that UPDATE/DELETE on `ticket_state_changes` fail. | OQ-09 (currency policy, seed only) |
| T-06 | **payment-sim service** per design §5.2: idempotent `POST /payments`, reserved tokens with the first/later-call behaviour table, `GET /payments/{key}` with `chargeCount`/`requestCount`, service-token auth, health endpoints, Dockerfile, compose/stack entry. | `simulators/payment-sim`, `infra/` | FR-08; D-05, D-11 | T-00 | Sim tests: same key+payload replays; different payload → 409; each token behaves per the table; `chargeCount` stays 1 across replays; state survives a restart (per OQ-03 outcome). | **OQ-03** |
| T-07 | **Payment client** `purchases/clients.py`: maps sim responses to exactly three results — `APPROVED`, `DECLINED`, `UNCERTAIN` (timeout, connection error, 5xx, malformed body, unexpected 4xx). | `ticketing-service/purchases` | FR-08, 10, 11; NFR-03; D-06 | T-03, T-06 | Unit tests for every mapping row using a stub server; no code path returns a definitive result for an uncertain response. | OQ-03 |
| T-08 | **Services/selectors:** `create_purchase` (design §6.1), `finalize_approved` / `finalize_declined` (design §6.2), `claim_due_purchases` (§6.3), domain exceptions. Event enqueued in the finalize transaction with `uuid5` event id. | `ticketing-service/purchases` | FR-02..12, 16, 17; NFR-01 | T-04, T-05, T-07 | Unit tests (fake payment client + fake clock) cover AS-01..AS-05 and AS-10..AS-14 outcomes; finalize is a no-op when already terminal; lock-then-check-then-write order verified. | — |
| T-09 | **API:** serializers (request + response), views, permissions, urls, drf-spectacular annotations for `GET ticket-types`, `POST purchases`, `GET purchases/{id}`; responses per design §5.1; `Location` and `Retry-After` on 202. | `ticketing-service/purchases/api`, `ticket_types/api` | FR-01, 02, 03, 13, 14, 16 | T-02, T-08 | Endpoint tests for every row of the §5.1 outcome table; OpenAPI generated and committed; views contain no business logic. | **OQ-01** (202 vs 503 rows) |
| T-10 | **Reconciler role:** `manage.py reconcile_purchases` (one foreground process), backoff + jitter + lease, alert hook for age > threshold, container/stack role definition. | `ticketing-service`, `infra/stack` | FR-12; D-12 | T-08 | Runs for two instances concurrently in a test without double finalization; stack definition committed; threshold configurable through settings. | **OQ-02**, OQ-05 (threshold value) |
| T-11 | **Contracts and drift checks:** committed OpenAPI for ticketing (and payment-sim); event schema committed; pipeline step fails on drift; oasdiff against released contract; Pact consumer test for ticketing → payment-sim. | `contracts/`, CI | NFR-06 | T-09, T-06 | CI step fails when a generated contract differs from the committed one (demonstrated with a deliberate change); Pact file produced by ticketing and verified by payment-sim. | — |

## C. Validation

| ID | Task | Verifies | Depends | Done when |
|---|---|---|---|---|
| T-20 | **Unit tests** (`unit` marker, no DB/network) for service logic and the payment-result mapping. | AS-01..05, 10..14 | T-08 | All pass; each test marked with requirement IDs; no sleeps. |
| T-21 | **Integration tests** with real PostgreSQL (testcontainers): 10-way concurrent same-key requests; concurrent API + reconciler finalization; rollback of Tx2 leaves no ticket; constraint backstops. | AS-04, FR-09, NFR-01 | T-20, T-04 | Run 20× in a loop without a failure; counts match AS-04 (1 purchase, 1 ticket, 1 sim payment). |
| T-22 | **Integration with payment-sim container:** `sim_approve`, `sim_decline`, `sim_slow`, `sim_lose_response`, `sim_error`; assert via `GET /payments/{key}` that `chargeCount` is 1. | AS-01, 05, 06, 07 | T-06, T-21 | Each scenario asserts final purchase state, ticket count and `chargeCount`; polling with timeout, no fixed sleeps. |
| T-23 | **Failure tests** (`failure` marker): kill ticketing between payment response and Tx2 (fault-injection hook or container kill); stop payment-sim during a purchase; Toxiproxy latency above the read timeout; unrelated endpoints stay available. | AS-08, 09; NFR-02, 03 | T-10, T-22 | After recovery: tickets 1, outbox 1, sim `chargeCount` 1; unrelated endpoints answered during the outage. Status-code assertion for AS-09 follows OQ-01. |
| T-24 | **Broker-down and relay tests:** stop RabbitMQ, purchase succeeds, event pending; restore, event published with original `eventId`; crash between publish and mark-published produces a duplicate publication with the **same** `eventId`. | AS-16; NFR-02 | T-05, T-21 | Test passes against real RabbitMQ; purchase latency during the outage is not blocked by the broker. |
| T-25 | **Contract tests:** published message validates against `contracts/events` schema, envelope fields present, `correlationId` propagated, no personal data; OpenAPI drift test. | AS-17; NFR-06 | T-05, T-11 | Schema validation test green; deliberate field removal makes it fail. |
| T-26 | **System test** against the deployed dev stack through Traefik: happy path and replay using the payment-sim; correlation id visible in logs of both services. | AS-01, 02; NFR-05 | T-10, T-11 | Passes in the dev pipeline after deployment; CI log links to the run. |
| T-27 | **Error-shape and logging tests:** every error response matches the shape and echoes `X-Correlation-Id`; log capture shows `correlation_id` and no token values. | AS-18; NFR-04, 05 | T-03, T-09 | Tests green; redaction verified with a canary token string. |
| T-28 | **Mutation testing** (mutmut) on `create_purchase`, `finalize_*`, and the fingerprint comparison. | NFR-01, FR-04, 05 | T-20, T-21 | Report committed; surviving mutants either killed by new tests or justified in `review.md`. |
| T-29 | **Traceability generation:** every test carries `@pytest.mark.req`; generated matrix has no requirement without a test and no test without a requirement. | NFR-08 | T-20..T-27 | Generated report committed or published by the pipeline. |

## D. Deferred or explicitly not planned

| ID | Task | Reason |
|---|---|---|
| T-30 | Web purchase screen (select type, show price, send `expectedPriceCents`, show pending state with polling of `GET /purchases/{id}`; i18n keys, accessible, clears query cache on logout). | Out of this slice (requirements §1.3). Do only when the team puts the UI in scope (principle 12). |
| T-31 | Consumer-side redelivery test (same `eventId` twice → one effect). | Belongs to the first consumer of `TicketPurchased` (notification feature). |
| T-32 | Performance test of purchase. | No target exists (PUR-NFR-10, OQ-08). |
| T-33 | Update `tech-stack.md`/`conventions.md` after T-00 (reconciler role, payment-sim route and storage, 202 rule). | Do immediately after T-00; listed so it is not forgotten. |

## E. Coverage check (scenario → tasks)

| Scenario | Implemented by | Verified by |
|---|---|---|
| AS-01 | T-04, T-08, T-09 | T-20, T-22, T-26 |
| AS-02 | T-08, T-09 | T-20, T-26 |
| AS-03 | T-08, T-09 | T-20 |
| AS-04 | T-04, T-08 | T-21 |
| AS-05 | T-07, T-08 | T-20, T-22 |
| AS-06, AS-07 | T-07, T-10 | T-22 |
| AS-08, AS-09 | T-10 | T-23 |
| AS-10, AS-11, AS-12, AS-13 | T-08 | T-20 |
| AS-14, AS-15 | T-02, T-09 | T-20, T-27 |
| AS-16 | T-05 | T-24 |
| AS-17 | T-05, T-11 | T-25 |
| AS-18 | T-03 | T-27 |
