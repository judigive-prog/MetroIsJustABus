# NFR-005 — Component responsibilities and boundaries

Version: 0.1 draft, 2026-11-11.
Issue: [MET-87](https://linear.app/metroisjustabus-ase/issue/MET-87).
Requirement: NFR-005 (Must), as recorded in Linear.
Baseline inspected: `969079ee45712a147cbab74a60f899b415efa02e` (MET-169).
Status: proposed for team review; model acceptance, deployment and runtime
verification remain pending.

## 1. Scope and sources

This document explains why responsibilities belong together and where they
communicate. The [domain/data model](../domain-data-ownership/design.md) is
the entity-level ownership reference; this document adds component boundaries,
interface responsibilities and architectural trade-offs.

Sources: the MET-87 acceptance criteria; the linked model and its
[assumption register](../domain-data-ownership/assumptions.md);
[principles](../../../steering/principles.md),
[conventions](../../../steering/conventions.md) and the
[adopted stack](../../../steering/tech-stack.md);
[purchase](../ticket-purchase/design.md) and
[validation](../ticket-validation/design.md) behavioural designs; and the
source paths listed in [review.md](review.md).
The original assignment and requirements PDFs were not independently inspected
for this change. Their interpretation follows the Linear/repository baseline,
not a new claim of teaching-staff approval.

Linear records a distributed solution and an independent notification
application as assignment constraints. The precise service decomposition,
broker product, database topology and protocols below are team design choices.
No open A-series assumption is approved here. MET-169 is still awaiting review.

## 2. Architecture and responsibilities

The following is the intended architecture, not a deployment inventory.
Arrows are labelled by their role; bidirectional HTTP responses are implicit.

```text
Browser (passenger/staff) -- HTTPS through ingress --> backend APIs
Validator/disruption simulators -- authenticated HTTP --> owning backend API

core-backend ---- owns ----> core database
ticketing-service -- owns -> ticketing database
occupancy-service -- owns -> occupancy database
notification-service owns -> notification database

ticketing-service -- synchronous HTTP --> payment-sim --> simulator database
core/ticketing -- local outbox --> relay -- AMQP --> RabbitMQ
RabbitMQ -- separate consumer queues --> occupancy / notification
notification -- persisted delivery attempts / SMTP --> sandbox mail server
```

| Component | Responsibilities and authoritative data | Boundary and exclusions |
|---|---|---|
| Web application | Public consultation, passenger account/ticket/subscription views and staff UI; temporary client state and allowlisted public cache | Calls owning APIs; no database access, authoritative role decisions, ticket-validity decisions or occupancy calculation. UI role checks only control presentation. |
| Core backend | Identity, profiles and roles; lines, stops, route patterns, ordered stops, schedules, variants, dated trips, operational state and disruptions; local audit/history | Owns network/trip identity and identity issuance. Does not own tickets, subscription delivery or occupancy attribution. A departure board is a core query, not a new shared database. |
| Ticketing and validation service | Ticket types, purchases, issued terms, ticket state/history, validation attempts and proposed validator registry; local audit/outbox | Makes ticket entitlement decisions in one local transaction. Stores passenger/stop UUID references, never queries core tables. Payment is an explicit external call; trip attribution is not a validation fact. |
| Occupancy service | Accepted boarding observations, proposed trip attribution, capacity, estimates and historical crowding | Owns the estimation rule and derived results, not validation truth or canonical trip identity. A-03 gates attribution; A-11 gates public crowding. No measured onboard count or proven over-capacity claim. |
| Notification service | Subscriptions and their effective history, preferences, recipient matching, deduplicated notification records, inbox/read state and delivery attempts | Independently deployable application with its own storage/API/workers. Does not modify tickets or core records; remote contact access uses an explicit minimized core interface. Channels await A-06. |
| Message broker | Durable transport and independent queues for consumer purposes | Owns no canonical business entities, entitlement rules or recipient logic. Persistence is not exactly-once processing or host-loss resilience. |
| Simulators | Validator/disruption stimuli through authorized APIs; payment-sim owns simulated provider outcomes keyed by an idempotent reference | No privileged database writes into services. Payment state is separate from purchase state; no real payment/card data. A-02/A-04/A-05/A-13 remain feature decisions. |

Ingress, SMTP sandbox and observability are supporting infrastructure, not new
business owners. The adopted stack selects Traefik for routing/TLS and Mailpit
for sandbox email. Authentication and authorization remain enforced by each
backend. Service identities are distinct from passenger/staff identities;
simulators do not bypass permission checks.

Each backend has its own image and database boundary. API, relay, consumer and
sender processes may share that backend image, but run separately when needed.
Independent notification deployment means its API/workers can be released or
restarted without releasing core/ticketing. This capability is a design target,
not demonstrated by the current checkout.

## 3. Interface ownership

These are logical interfaces, not accepted wire contracts. MET-88 will define
and version the machine-readable HTTP/message schemas and compatibility checks.
Existing route names are noted only where source code was inspected.

| Provider / consumer | Interface and purpose | Consistency, security and failure boundary |
|---|---|---|
| Core / web and backend services | Identity/authentication and public-key distribution; network, schedule, trip and disruption queries; authorized staff commands | Core alone changes its entities. Backends verify identity and enforce local permissions; no core DB joins. Key distribution, rotation, revocation and role freshness need a contract. |
| Ticketing / web | Ticket types, purchase submission/status, passenger tickets/history and staff ticket operations | Existing routes include `/api/ticketing/v1/ticket-types`, `/purchases` and `/purchases/{id}` under the same prefix. Other operations remain planned. Passenger UUID comes from authenticated identity; ownership checks are server-side. |
| Ticketing / validator | Validation command and accepted/rejected outcome with reason | Proposed validator registry binds authenticated device to a core stop UUID. No inferred line/trip. Time authority, credentials, replay comparison and entitlement rules await feature review. |
| Payment-sim / ticketing | Simulated payment at `/api/payment-sim/v1/payments` | Purchase UUID is the provider idempotency key in existing code. An uncertain outcome remains pending. No transaction spans both databases; purchase-owned reconciliation is required. |
| Core / broker consumers | Proposed `ScheduleChanged`, `DisruptionChanged`, `TripStatusChanged` events | Core commits changes/audit/outbox locally. Consumers need effective scope, identity and time information; schema completeness is verified in MET-88, not assumed here. |
| Ticketing / broker consumers | `TicketPurchased` and proposed `TicketValidated` activity events | Existing `TicketPurchasedV1` model is source evidence, not a deployed contract. Only accepted validation activity contributes to boarding estimates; retries preserve event identity. |
| Occupancy / web | Authorized staff indicators and proposed public trip/crowding queries | Explicit estimate, freshness and completeness metadata; no fabricated zero when data is unavailable. Public visibility awaits A-11. |
| Notification / web | Subscription/preference commands, passenger inbox/read state | User-scoped authorization; event-time subscription/preference history for FR-068. Core target identity validation uses an explicit API/projection, not a database FK. |
| Core / notification and occupancy | Minimized contact interface and versioned network/trip projections as needed | Contact data is restricted to delivery purposes. Projection bootstrap, event gaps and reconciliation are contract/design obligations before implementation; consumers never become canonical owners. |
| Notification / channel adapter | Persisted delivery attempts; SMTP only if sandbox email is confirmed | Unique event/user/channel records prevent duplicate notifications. Uncertain SMTP delivery can duplicate email on retry; inbox deduplication cannot guarantee exactly-once external delivery. |

`packages/metro_common` may contain versioned event types and technical
logging/correlation helpers. It must not contain shared ORM models, business
services, database access or a shared authority for ticket/occupancy decisions.
Consumers must remain compatible across supported released contract versions;
updating every service in the monorepo together is not proof of independence.

## 4. Behaviour and transaction boundaries

These summaries connect the ownership model to existing feature designs.
Detailed state/interaction/failure models belong to MET-170 and each feature.
They describe intended behaviour, not executed tests.

### Purchase and an uncertain payment

1. Ticketing authenticates the passenger and resolves the request idempotency
   key, then commits a pending purchase with immutable terms/price.
2. It calls payment-sim outside the database transaction with the purchase UUID
   as the stable provider key. A timeout does not prove payment failed.
3. On confirmed approval, one ticketing transaction locks the purchase and
   records the ticket, state change, completion and `TicketPurchased` outbox
   intent. A decline issues no ticket; uncertainty stays pending for later
   reconciliation using the same provider identity.
4. A separate relay eventually publishes the outbox event. Notification/broker
   failure does not roll back the purchase or make the request wait for delivery.

See [purchase design](../ticket-purchase/design.md), especially its transaction,
payment and reconciliation boundaries. Existing code has no completed
reconciler/relay demonstration; no eventual recovery is claimed as observed.

### Validation and occupancy

The [validation design](../ticket-validation/design.md) proposes a local
ticket lock, entitlement decision, attempt record, accepted state change and
outbox intent in one ticketing transaction. Replays must not spend another
journey. Neither occupancy nor notification participates in that transaction.
Occupancy later consumes accepted activity and deduplicates by event ID in the
same transaction as its local effect. Distinct activity events must not be
dropped merely because they arrive out of order.

The [domain model, section 5](../domain-data-ownership/design.md#5-boarding-and-occupancy)
separates observation from attribution. A stop observation does not identify
the boarded trip. A-03/A-05/A-13 must be resolved before implementing the
attribution or treating the proposed validator payload as approved.

### Disruption and independent notification

Core validates a staff command and commits the disruption, change/audit record
and outbox intent. Its query layer applies the operational overlay while
preserving the published schedule. The notification consumer processes the
change using subscriptions/preferences effective at event time, stores its
inbox marker and deduplicated notifications in one local transaction, then
acknowledges. A separate sender handles delivery attempts.
Notification outage delays notification, not core's disruption command.
Overlapping-disruption precedence and subscription target identity remain
open model decisions; these are not silently selected here.

| Failure | Boundary and intended response |
|---|---|
| Broker or downstream consumer unavailable | Owning database retains outbox intent; relay retries with the same event ID. Consumer outage must not block purchase/validation. Requires intact persistent storage and later verified recovery. |
| Duplicate delivery / consumer crash | Inbox ID and business effects commit together before acknowledgement; redelivery has no second effect. Activity and state snapshots have different ordering semantics. |
| Poison message | Bounded retries and inspectable DLQ; no infinite requeue loop or silent discard. Retry/DLQ transfer must preserve messages. |
| Core or signing-key distribution unavailable | Operations requiring fresh core data may be unavailable. Verification with valid cached keys is possible only under an agreed cache/rotation policy; do not accept unverifiable tokens. Existing code uses a configured key file. |
| Occupancy unavailable or stale | Estimates visibly unavailable/stale; ticket validation continues. No guessed zero or measured occupancy claim. |
| Owning database or host/storage lost | That owner's writes cannot succeed safely. Outbox/inbox does not replace backup/restore or provide high availability; recovery evidence is separate work. |

## 5. Architectural decisions and alternatives

The stack choices below already appear in steering. MET-87 explains their
responsibility implications; it does not claim new team approval.

| Decision and rationale | Alternative considered | Trade-off / revisit trigger |
|---|---|---|
| Keep core and supporting applications independently deployable, with a separate notification application | One backend containing every feature | A single all-functionality backend conflicts with the assignment interpretation recorded in Linear and couples releases/failures. Distributed components add contracts, authentication and operational cost; demonstrate independence in BOOT-01. |
| Keep purchase, ticket terms/state and validation together in ticketing | Separate purchase and validation databases/services | Co-location keeps the per-ticket consistency invariant within one PostgreSQL transaction. Splitting adds distributed coordination for little current benefit; revisit only if ownership or scale justifies that cost. |
| Keep recipient matching, subscriptions, inbox and delivery in notification | Send email directly from core/ticketing request handlers, or use a stateless SMTP helper alone | A helper does not own event-time preferences, deduplication, inbox and retries. The independent application isolates channel outages but adds eventual consistency and sensitive contact-data handling. |
| Keep occupancy-derived data separate from validation truth | Compute trip occupancy synchronously during validation | Attribution is provisional and may change; an estimation outage must not reject a valid ticket. Separate processing adds lag, projection recovery and explicit freshness semantics. |
| Core owns network/trip and identity facts; services retain UUIDs/projections | Shared schema and cross-service joins | Local joins are simpler but couple schema, access privileges and deployment. Separate databases require explicit consistency/reconciliation and cannot enforce cross-owner FKs. Identity/key distribution is an availability/security dependency. |
| REST/JSON for immediate answers; RabbitMQ events with outbox/inbox for secondary effects | Synchronous downstream fan-out; direct publish after commit; Kafka | Fan-out couples outages; post-commit publishing risks event loss. RabbitMQ matches the adopted retry/queue model; Kafka adds operational scope without an established requirement. Outbox/inbox adds storage/workers and at-least-once handling, not exactly-once external effects. |
| Monorepo with technical shared package, independent build/release units | Polyrepo, or one shared domain-model package | Monorepo simplifies traceability and coordinated contract changes. Shared business/ORM code would couple owners; polyrepo adds coordination overhead. Version compatibility remains necessary regardless of repository layout. |

## 6. Review gates and traceability

Before accepting this design, the team must review Validator and TripCapacity
ownership, route/run identity and subscription targets against MET-169. Confirm
service credential issuance, identity claims/key lifecycle and contact-data
access before their contracts are implemented. Preserve the full
[A-01–A-14 register](../domain-data-ownership/assumptions.md), including retention
and account deletion coordination; no distributed delete policy is approved.

| Requirement / work item | Design evidence / handoff |
|---|---|
| NFR-005 / MET-87 | Sections 2–5: responsibilities, interfaces, behaviour and justified alternatives |
| MET-169, NFR-032 / MET-106 | Canonical linked entity ownership model; section 2 maps it to applications |
| NFR-001–004 | Independent supporting components, private storage and explicit interfaces; implementation/deployment evidence remains pending |
| NFR-006 / MET-88 | Section 3 interface inventory is input to machine-readable contracts; no generated schemas added here |
| NFR-013–015, NFR-020–022, NFR-030–031 | Section 4 local atomicity, durable secondary work, deduplication and explicit estimation lag; runtime checks pending |
| FR-060–069, NFR-050/053/056 | Notification boundary, event-time matching, authorization and minimized contact access; channel/identity decisions pending |
| FR-081/103/105 | Linked immutable terms, historical models and stable/operational separation; A-09 retention still open |
| MET-170 / MET-171 | Behaviour summaries inform detailed models and the minimal runnable distributed slice; neither is completed by documentation |

See [review.md](review.md) for source evidence, remaining findings and acceptance
status. No model approval, human review, passing integration test or deployment
is inferred from writing this document.
