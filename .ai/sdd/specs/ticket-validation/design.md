# Ticket Validation — Design

**Status:** preliminary (PL6, 2026-10-27). Based on [requirements.md](requirements.md) and the steering files. Not implementation-ready until the team confirms the *proposed* decisions.

## 1. Components and responsibilities

The feature lives in one component. It needs no synchronous call to another service.

| Component | Role in this feature |
|---|---|
| `validator-sim` (or a real validator) | Reads the ticket id and calls the validation API with its service token and an idempotency key |
| Traefik | Routes `/api/ticketing/...` and terminates TLS (existing) |
| `ticketing-service` API | Authenticates the validator, decides, records, updates the ticket and writes the outbox event in one transaction |
| Ticketing PostgreSQL | Tickets, validators, validation attempts, ticket state changes, `outbox_event` |
| Ticketing outbox relay | Publishes pending events to RabbitMQ. Shared infrastructure, **outside this feature** |
| `occupancy-service` | Consumes `TicketValidated` later. **Outside this feature** |

```mermaid
sequenceDiagram
  participant V as Validator
  participant API as ticketing API
  participant DB as ticketing DB
  participant R as outbox relay
  participant MQ as RabbitMQ
  V->>API: POST /api/ticketing/v1/validations (token, Idempotency-Key)
  API->>API: authenticate validator, look up its stop
  API->>DB: BEGIN; lock ticket row (SELECT ... FOR UPDATE)
  API->>DB: existing attempt for (validator, key)?
  alt key already used
    DB-->>API: stored attempt
    API-->>V: 200 stored response (or 409 if payload differs)
  else new request
    API->>API: evaluate rules at clock.now()
    API->>DB: insert validation_attempt
    opt accepted
      API->>DB: update ticket, insert ticket_state_change, insert outbox_event
    end
    API->>DB: COMMIT
    API-->>V: 200 ACCEPTED or REJECTED + reason
  end
  R-->>MQ: TicketValidated (later, asynchronous)
```

## 2. Domain entities (ticketing database)

All tables have `id` (UUID), `created_at` and `updated_at` per conventions.

**`validators`** (owned by ticketing; see OQ-04)
- `stop_id` (UUID of a core-backend stop; no foreign key across services)
- `status`: `ACTIVE` | `INACTIVE`
- `code` (human label)

**`tickets`** (created by the purchase feature; columns this feature reads or changes)
- `terms` (JSON, immutable snapshot taken at issue): `journeys` (int or null), `period_minutes` (int or null), `expires_at` (UTC or null)
- `status`: `ISSUED` | `ACTIVE` | `USED_UP` | `EXPIRED` | `CANCELLED`
- `remaining_journeys` (int or null)
- `activated_at`, `valid_until` (UTC or null; set at first accepted validation when `period_minutes` is set)
- `version` (int, incremented on every change; used in event snapshots)
- Check constraint: `remaining_journeys >= 0`

**`validation_attempts`** (append-only)
- `validator_id`, `stop_id` (copied from the validator at decision time)
- `idempotency_key` (UUID), `payload_hash`
- `presented_ticket_id` (UUID as received), `ticket_id` (null when unknown)
- `result`: `ACCEPTED` | `REJECTED`; `reason` (null when accepted)
- `decided_at` (server clock), `device_time` (as sent)
- `response` (JSON body returned, for exact replay)
- Unique constraint `uq_validation_attempt_validator_key` on (`validator_id`, `idempotency_key`)

**`ticket_state_changes`** (append-only): `ticket_id`, `from_status`, `to_status`, `cause` (`VALIDATION`), `validation_attempt_id`, `occurred_at`

**`outbox_event`**: per conventions

The attempt table serves as both the validation record (FR-043, FR-047) and the idempotency store, so there is no separate idempotency table. Retention: attempts are history and are kept (FR-103); A-09 retention applies when decided.

## 3. Interfaces

### 3.1 REST: `POST /api/ticketing/v1/validations`

Headers: `Authorization: Bearer <validator service token>`, `Idempotency-Key: <UUID>`, optional `X-Correlation-Id`.

Request:
```json
{ "ticketId": "8f1c…", "deviceTime": "2026-11-20T08:00:03Z" }
```

Response `200`:
```json
{
  "validationId": "c2a9…",
  "result": "ACCEPTED",
  "reason": null,
  "decidedAt": "2026-11-20T08:00:01Z",
  "ticket": { "status": "ACTIVE", "remainingJourneys": 9, "validUntil": null }
}
```
For `REJECTED`, `reason` is one of `UNKNOWN_TICKET`, `CANCELLED`, `EXPIRED`, `NO_JOURNEYS_LEFT`, and `ticket` is null when the ticket is unknown.

Errors use the standard error shape: `400` malformed body or missing key; `401` no or invalid token; `403` not a validator, or validator inactive; `409 IDEMPOTENCY_KEY_REUSED`; `503 DEPENDENCY_UNAVAILABLE` when the database is unreachable.

### 3.2 Event: `TicketValidated` v1

Routing key `ticketing.ticket.validated`, standard envelope, written to the outbox in the validation transaction. Semantics: **activity event**, processed once per `eventId`, order not significant.

```json
{ "validationId": "c2a9…", "validatorId": "…", "stopId": "…", "validatedAt": "2026-11-20T08:00:01Z" }
```
No ticket id and no passenger id (D-08). Schema goes in `contracts/events/`.

## 4. Decision procedure

Inside `transaction.atomic()`:

1. Resolve the validator from the token. If missing or `INACTIVE`, return `403` (no record).
2. Compute `payload_hash` from `ticketId` only. `deviceTime` is excluded: a validator may read its clock again when it retries, and that must still count as the same request (review finding F-03).
3. If the ticket exists, lock it with `select_for_update()`.
4. Look up an attempt with (`validator_id`, `idempotency_key`). If found: same hash → return its stored `response`; different hash → `409`.
5. `now = clock.now()`. Evaluate in this order (TV-REQ-03):
   1. ticket not found → `UNKNOWN_TICKET`
   2. `status == CANCELLED` → `CANCELLED`
   3. `terms.expires_at` set and `now >= expires_at`, or `valid_until` set and `now >= valid_until` → `EXPIRED` (append state change to `EXPIRED` if not already)
   4. `status == USED_UP`, or `remaining_journeys == 0` → `NO_JOURNEYS_LEFT`
   5. otherwise → `ACCEPTED`
6. If accepted: if `status == ISSUED`, set `ACTIVE`, `activated_at = now`, and `valid_until = now + period` when a period exists; if a journey limit exists, decrement `remaining_journeys` and set `USED_UP` at 0; increment `version`; append state changes; write the outbox event.
7. Insert the attempt with the response. If the insert hits `uq_validation_attempt_validator_key` (a parallel request with the same key and an unknown ticket, which has no row to lock), roll back, re-read the stored attempt and replay it.

The rule evaluation (step 5) is a pure function of the terms, the ticket state and `now`, so it can be unit-tested and mutation-tested without a database.

## 5. Failure handling, consistency and security

| Case | Behaviour |
|---|---|
| Validator times out and retries with the same key | Step 4 replays the stored result; no second effect (TV-AC-09) |
| First request never reached the server | The retry is a first request and is decided at its own server time (D-02) |
| Two validators, same ticket, same moment | Row lock serialises them; the second sees the updated ticket (TV-AC-11) |
| Same key, parallel, unknown ticket | Unique constraint plus replay (step 7) |
| Broker or occupancy down | Unaffected: the event waits in `outbox_event` (TV-AC-12) |
| Database down | `503`, nothing stored; a retry with the same key works later (TV-AC-15) |
| Crash after commit, before the response | The retry replays the stored response |

- **Consistency:** strong within ticketing (one transaction, row lock). Occupancy is eventually consistent (NFR-031).
- **Security:** the default permission denies; the view allows only the `validator` service role. Stop and time come from the server, not the device (D-02, D-03). Logs carry `correlation_id` and the attempt id, not passenger data.
- **Performance:** one row lock and four inserts per accepted validation; no remote call. Lock contention only occurs on the same ticket.

## 6. Decisions and alternatives

| Decision | Alternatives considered | Why this one |
|---|---|---|
| Server time is authoritative (D-02) | Trust device time; accept device time within a skew tolerance | Device clocks can drift or be tampered with, and a tolerance adds a number nobody has asked for. Validators are online (D-09) |
| Row lock on the ticket (`SELECT … FOR UPDATE`) | Optimistic locking on `version` with retry; serializable isolation | Contention is per ticket and rare; a lock is simpler and gives a deterministic result. Matches principle 1 |
| Attempt table doubles as the idempotency store | Separate generic idempotency table | One insert fewer, and the stored response is the record itself. Purchase may still need a generic store |
| Unknown ticket → `200 REJECTED` (D-06) | `404 TICKET_NOT_FOUND` per the general convention | FR-042 names it as a rejection reason; the validator treats every refusal the same way |
| No ticket id in the event (D-08) | Include ticket id and type | Occupancy does not need them; less personal data travels |

## 7. Unresolved questions

See OQ-01 to OQ-06 in [requirements.md](requirements.md#8-open-questions). OQ-03 (credential issuing) affects implementation; the others do not block PL7.
