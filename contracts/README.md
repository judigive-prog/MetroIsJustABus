# Versioned interface contracts — MET-88 / NFR-006

Status: initial contracts and local checks prepared for team review.
See [review.md](review.md) for executed evidence and limitations. MET-87 approval
and human acceptance remain pending.

## Scope

These contracts cover the HTTP interfaces and event producer present in this
checkout. They describe existing behaviour and do not implement features or
approve unresolved assumptions. Sources are the
[component boundaries](../.ai/sdd/specs/component-boundaries/design.md),
[domain model](../.ai/sdd/specs/domain-data-ownership/design.md),
[conventions](../.ai/steering/conventions.md),
[adopted stack](../.ai/steering/tech-stack.md) and the source paths below.

| Interface | Source | Contract / example |
|---|---|---|
| Ticket type listing, purchase creation/status | `apps/ticketing-service/ticket_types/api/`, `purchases/api/` | [Ticketing OpenAPI](openapi/ticketing.v1.json) |
| Simulated payment creation/inspection | `simulators/payment-sim/payments/api/`; client in `apps/ticketing-service/purchases/clients.py` | [Payment OpenAPI](openapi/payment-sim.v1.json), [HTTP exchange](examples/payment.v1.json) |
| TicketPurchased v1 | `packages/metro_common/metro_common/events/`; builder in `apps/ticketing-service/purchases/services.py` | [JSON Schema](events/ticket-purchased.v1.schema.json), [AsyncAPI](events/ticketing.asyncapi.v1.json), [synthetic example](examples/ticket-purchased.v1.json) |
| Core, validation, occupancy, notification APIs and other events | Architecture/feature proposals | Pending implementation and relevant decisions; no endpoints or payloads invented here |

DRF serializers and annotations are the HTTP source; Pydantic models are the
event payload/envelope source. The event generator specializes the generic
envelope with the concrete payload and its type/version/producer metadata.
AsyncAPI records the adopted AMQP exchange and routing key as a design, not as
evidence of an existing broker/relay. Health checks are operational endpoints,
not part of these generated DRF business contracts.

## Reproduce

Run from the repository root. Install uv, then prepare all three isolated
Python 3.13 environments using the committed lockfiles:

```bash
uv sync --locked --python 3.13 --project packages/metro_common --group contracts
uv sync --locked --python 3.13 --project apps/ticketing-service --group contracts
uv sync --locked --python 3.13 --project simulators/payment-sim
```

The optional `contracts` groups contain verification tooling. They are not
publishing-service runtime requirements. Payment-sim additionally uses
`drf-spectacular` at runtime for its schema annotations, matching ticketing's
existing approach. Virtual environments and Python caches are ignored by Git.

To regenerate after an intentional source change:

```bash
uv run --locked --project packages/metro_common python contracts/generate_events.py
uv run --locked --project packages/metro_common python contracts/generate_events.py --asyncapi
uv run --locked --project apps/ticketing-service python contracts/generate_openapi.py
uv run --locked --project simulators/payment-sim python contracts/generate_openapi.py --service payment-sim
```

For each generator, append `--check` to compare without writing. OpenAPI
generation rejects warnings and validates the document against OpenAPI.
The offline configuration reads literal schema-relevant settings from source
without executing the runtime settings module or reading its secret files.
A dummy database backend prevents real database access.

Run the checks:

```bash
uv run --locked --project packages/metro_common --group contracts python contracts/validate_events.py
uv run --locked --project apps/ticketing-service --group contracts python contracts/check_payment_contract.py
uv run --locked --project apps/ticketing-service --group contracts python contracts/check_event_contract.py
uv run --locked --project packages/metro_common --group contracts python contracts/validate_asyncapi.py
```

The payment check starts payment-sim in a separate process using its prepared
virtual environment. It exercises the real ticketing client, provider route,
authentication and serializers. Only the payment business operation is stubbed;
no socket or database is used. The checked OpenAPI 3.0 request/response schemas
use a Draft 4-compatible subset; this is not a general instance validator for
OpenAPI-specific keywords such as `nullable`, `readOnly` and `writeOnly`.

The event boundary check calls the existing producer with unsaved synthetic
model instances, then passes JSON to a schema-only receiver in another Python
environment. It prints the exchanged message, contract type/version and
result. That receiver is a test probe, not notification-service.

AsyncAPI validation downloads an official meta-schema at a fixed Git revision
and verifies its SHA-256. It then checks document structure, internal references,
routing metadata, external event schema and embedded example. It needs HTTPS
access to the pinned GitHub file, not a broker or application credentials.
The referenced message uses JSON Schema Draft 2020-12, explicitly declared
through AsyncAPI's multi-format mechanism; tools need support for that dialect.

The added `contracts` job in the existing CI workflow prepares locked
environments and runs generation drift and boundary/example checks. Existing
workflow triggers are preserved: PR checks target `main`. A stacked PR targeting
MET-87 does not gain a successful GitHub check merely because local checks pass;
verify CI when the PR targets `main`. CI execution remains pending until observed.

## Versions and compatibility

- HTTP route major is `/v1/`; OpenAPI `info.version` is `1.0.0`. This is a
  first recorded contract, not a claim of compatibility with an older release.
- Event `version: 1` identifies the event schema. It is distinct from an entity
  version used to order state snapshots. TicketPurchased is activity.
- Additional fields remain tolerated. Missing required fields, incorrect types,
  unsupported event discriminators and invalid UUID/timestamp formats are tested.
- Breaking changes require a new major and coexistence while supported consumers
  migrate. Compare future candidates against each supported released baseline
  and test relevant provider/consumer combinations during rollout and rollback.
- Drift checks, example validation, compatibility probes and deployed integration
  tests provide different evidence; none substitutes for the others.

## Limits and source gaps

There is no implemented notification consumer or broker round trip in these
checks, no tested payment persistence/idempotency and no prior released-version
baseline. Full deployed consumer compatibility and delivery guarantees remain
feature/system-test work. No actual personal information or credentials appear
in the examples.

Contracts mirror current models rather than silently adding business rules.
For example, the existing event model does not constrain currency to an ISO
code or price to a nonnegative value; schema validation alone does not establish
those business invariants. Runtime serializers and business logic remain
necessary even when a document is structurally valid.

## References

- [drf-spectacular schema customization](https://drf-spectacular.readthedocs.io/en/latest/customization.html)
- [Pydantic JSON Schema generation](https://docs.pydantic.dev/latest/concepts/json_schema/)
- [AsyncAPI 3.0.0 specification](https://www.asyncapi.com/docs/reference/specification/v3.0.0)
- [AMQP binding specification](https://github.com/asyncapi/bindings/blob/master/amqp/README.md)
