# Conventions — MetroIsJustABus

The patterns beyond the linter. Numeric defaults (timeouts, page sizes, retry counts) are starting points: change them here when a performance test or a feature spec says otherwise. Where a feature spec is approved and conflicts with this file, stop and ask which one to update.

## API (REST, DRF)
- Routes: `/api/{service}/v1/{resource}`, resource plural and kebab-case. Services: `core`, `ticketing`, `occupancy`, `notifications`. Example: `/api/ticketing/v1/purchases`
- Staff-only endpoints live under `/api/{service}/v1/staff/{resource}`. Passenger and public endpoints never share a path with staff ones
- Every endpoint has a request serializer, a response serializer and a drf-spectacular annotation. No endpoint without a declared response schema
- Views are thin: authenticate, validate with the serializer, call one function in `services.py` or `selectors.py`, map the result
- Errors follow one shape, produced by a single exception handler:
  `{ "error": { "code": "TICKET_NOT_FOUND", "message": "...", "correlationId": "..." } }`
- Codes: 400 validation, 401 no auth, 403 no permission, 404 not found, 409 conflict, 422 business rule, 429 throttled, 500 unexpected failure, 503 dependency unavailable. `message` is readable by passengers and never exposes internals (NFR-063). Unexpected failures are logged with their correlation id; the response contains a generic message. Throttled responses include `Retry-After`
- A ticket validation that is rejected is a normal outcome, not an error: `POST /api/ticketing/v1/validations` returns 200 with `{ "result": "REJECTED", "reason": "EXPIRED" }`. Ticket-validity decisions use this outcome; malformed requests, authentication, permissions, missing resources and idempotency conflicts use the appropriate 4xx response
- Permissions are explicit on every view. The default permission class denies; public endpoints declare `AllowAny` on purpose
- Retry-safe writes (purchase, validation) require an `Idempotency-Key` header (UUID). Same key and same payload replays the stored terminal response. Same key and different payload returns 409 `IDEMPOTENCY_KEY_REUSED`. Keys are scoped per caller and operation, with uniqueness enforced in the database
- Before implementation, each retry-safe operation's design defines payload comparison, concurrent requests with the same key, pending-operation responses, retention and expiry, and retryable versus terminal failures. An uncertain payment outcome stays pending until reconciled; a retry never starts a second payment or issues a second ticket. A transient dependency failure must not become a permanently replayed terminal result
- Lists use `limit` and `cursor` (default limit 50, max 200). History lists (validations, notifications, disruptions) are ordered newest first
- IDs are UUIDs. Lines and stops also have a human `code` for display and search
- Timestamps are ISO 8601 in UTC with `Z`. Timetable times (a schedule's time at a stop) are local `HH:MM:SS` on a service date in `OPERATING_TIMEZONE`
- The validation design must define the authoritative decision time, handling of validator clock skew and delayed submissions, and how an authenticated validator is bound to a stop. Do not trust a device-supplied time or stop without the approved validation rules
- Every request carries `X-Correlation-Id`. Create it if missing and return it in the response
- Additive, backward-compatible changes stay in `v1`. A breaking change needs `v2`, served alongside `v1` until all supported consumers have migrated. Compare each supported version with its released contract and verify consumers against the provider versions they may encounter during rollout or rollback. The committed OpenAPI file must match the generated one

## Calls between components
- All outbound HTTP goes through one shared client wrapper with timeouts (connect 1 s, read 3 s) and the correlation id header. No bare `requests` calls
- Retry only idempotent calls, at most 3 times, with exponential backoff and jitter. A write is retried only when it carries an `Idempotency-Key`
- When a dependency is down, return 503 `DEPENDENCY_UNAVAILABLE`. Never hang, and never return a guess
- Service-to-service and simulator calls send a service token. They never use a passenger or staff token

## Database (PostgreSQL, Django ORM)
- Explicit `db_table`: plural snake_case, except the fixed event table names `outbox_event` and `inbox_event`. Columns snake_case
- Every model has `id` (UUID), `created_at`, `updated_at`. Each service defines its own abstract base for this. Nothing is shared across services
- Datetimes use timezone-aware `DateTimeField` and are stored in UTC. Never use naive datetimes or `datetime.now()`
- Money is an integer in minor units (`price_cents`) plus a currency code. Never float
- Uniqueness and validity rules are database constraints, with explicit names: `UniqueConstraint`, `CheckConstraint`
- No hard deletes of business data. Lines, stops and ticket types are deactivated or retired. Other entities have an explicit `status`
- Append-only tables (validations, ticket state changes, disruption changes, staff audit log) get no UPDATE and no DELETE
- A ticket stores an immutable copy of its ticket type's terms at issue, so later type changes never alter those terms (FR-081). Operational state, such as activation, remaining journeys and lifecycle status, changes through business operations that append a state-change record
- No foreign keys across services. Refer to another service's entity by UUID only
- Migrations are never edited after they are merged. Schema changes follow expand/contract. Migrations run as a pipeline step before deployment, never at application start-up
- Event tables use fixed names: `outbox_event` and `inbox_event`. Each service has its own pair

## Code (Python)
- Service layout: `models.py`, `services.py` (writes and business rules), `selectors.py` (reads), `api/` (views, serializers, permissions, urls), `events/` (publishers, handlers), `tests/`
- Functions in `services.py` take plain data and return data. They never see the HTTP request. They raise domain exceptions (`TicketExpired`), and the exception handler maps them to responses
- Anything that changes more than one table runs inside `transaction.atomic()`. Lock first, then check, then write: validation locks the ticket row, decides, records, and writes the outbox event in the same transaction
- Time comes from an injectable clock (`clock.now()`), never from `timezone.now()` called inline. Validity depends on the time of use, so tests must control it
- Configuration comes only from the settings object (pydantic-settings). No `os.environ` reads elsewhere. No secrets in code or in committed files
- Type hints on every function. mypy and ruff pass with no new ignores. An `Any` or `# type: ignore` needs a one-line reason
- Logs use structlog with snake_case event names (`ticket_validation_rejected`) and always carry `correlation_id`. Never log passwords, tokens or personal data (NFR-056)
- Staff actions that change network, tickets or disruptions write an audit record in the same transaction (NFR-057, FR-095)

## Events (RabbitMQ)
- One durable topic exchange, `metro.events`. Routing key: `{service}.{entity}.{action}` (`ticketing.ticket.validated`). Event type names are PascalCase past tense (`TicketValidated`)
- Queue per consumer purpose: `{consumer}.{purpose}`. Retry queues `{queue}.retry.{n}` with a TTL. Dead-letter queue `{queue}.dlq`
- Declare queues, exchanges and bindings before publishing; business, retry and dead-letter queues are durable. Publish persistent messages with publisher confirms and mandatory routing. Mark an outbox event published only after confirmation and no routing return. Unconfirmed or unroutable events remain pending for retry and raise an operational alert; retries preserve `eventId`. Retry and dead-letter transfers must also preserve messages if their destination is unavailable, using supported at-least-once dead-lettering or confirmed republishing before acknowledging the original delivery
- Envelope: `eventId` (UUID), `type`, `version`, `producer`, `occurredAt` (UTC), `correlationId`, `payload`
- Payload carries what consumers need to act without calling back. State snapshots include an entity `version`, distinct from the envelope's schema `version`; projections never replace newer state with an older snapshot. Distinct activity events, such as accepted ticket validations, are processed once per `eventId` even if they arrive out of order. Delta events need an explicit gap-handling or reconciliation rule. Each event contract declares its semantics
- Publish only through the outbox helper, called inside the transaction that changes state. Never publish straight from a view after commit
- A consumer checks `inbox_event` first, handles the event, and acknowledges only after the database commit. A repeat of the same `eventId` has no effect
- A failing event is retried with backoff, then sent to the DLQ. A poison message never blocks its queue and is never requeued in a loop
- Schemas live in `contracts/events`. Within a version, changes are additive and consumers ignore unknown fields. A breaking change is a new `version`, published alongside the old one during the transition
- Notification-record dedupe key: (`eventId`, `userId`, `channel`), enforced by a unique constraint (FR-066). Overlapping subscriptions to the same change produce one record per user and channel (FR-065). In-app inbox records are deduplicated; SMTP delivery uses retries and may duplicate after an uncertain send outcome. Record delivery attempts and status separately from notification creation; do not claim exactly-once e-mail delivery

## Web (React)
- TypeScript strict, no `any`. Use `unknown` and narrow
- API calls use only the shared `openapi-fetch` client typed with generated `openapi-typescript` types. Server state lives in TanStack Query, never copied into other stores
- Persist only an allowlist of public consultation queries. Account, ticket, subscription, notification and staff data stay in memory, with query keys scoped to the authenticated user. On logout or account change, cancel outstanding requests and clear the query cache before showing another session; never persist tokens in the query cache
- All user-visible text is an i18n key. No hard-coded strings
- Role checks in the UI only hide controls. The server decides (FR-101, FR-102)
- When a refresh fails and cached data is shown, display the stale-data banner with a short message (NFR-024). Show `error.message` mapped from `error.code`, never raw responses
- Accessibility: semantic HTML, a label on every input, visible focus, no information carried by colour alone (NFR-061)

## Containers and configuration
- Multi-stage Dockerfiles, non-root user, base images pinned by tag and digest. Never `latest`
- Every service exposes `/health/live` and `/health/ready`. Readiness fails when a required dependency is missing
- Environment variables are UPPER_SNAKE_CASE. Secrets arrive as `*_FILE` paths
- Image tag = git SHA. The same image goes to dev and prod
- Environments change only through version-controlled configuration and the pipeline, never by hand (NFR-094, NFR-097)

## Tests
- Tests sit in a `tests/` folder inside the module they cover: `test_{behaviour}.py`
- pytest markers: `unit` (no database, no network), `integration` (real PostgreSQL and RabbitMQ), `contract`, `system`, `failure`
- Every test that verifies a requirement carries `@pytest.mark.req("FR-045")`, so requirement-to-test traceability can be generated (NFR-087)
- Every retry-safe operation has a test that sends the same request twice and asserts one effect, and a test that redelivers the same event and asserts one effect
- Tests never sleep to wait for events. They poll with a timeout

## Git and traceability
- Branches: `feat/{component}-{short-name}`, `fix/...`, `chore/...`. Commits follow Conventional Commits with the component as scope: `feat(ticketing): reject expired tickets`
- Every commit message carries trailers: `Req: FR-041, FR-042` and, when an agent produced or changed the code, `Agent: {tool}/{model}` and `Human-Intervention: none | edited | rewritten`
- A pull request lists the requirement IDs it covers, the tests that verify them, and the contract files it changes. The pipeline must pass before merge
- AI-generated changes are reviewed like any other change. Review effort and rework are recorded (NFR-112 to NFR-114)
