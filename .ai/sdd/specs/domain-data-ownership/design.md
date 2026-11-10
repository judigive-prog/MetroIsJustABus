# DES-01 — Domain, data and ownership models

Version: 0.1 draft, 2026-11-10.
Issue: [MET-169](https://linear.app/metroisjustabus-ase/issue/MET-169).
Status: proposed for team review; no approval, schema implementation or deployment claimed.

## Scope and evidence

This document models the whole domain because MET-169 explicitly requires it.
Its changes are design artefacts only. APIs, Django models/migrations, seed
commands, contracts and CI changes belong to their respective later issues.

Sources inspected:
- The current MET-169 acceptance criteria and its MET-168 dependency.
- [Product vision](../../../steering/product.md),
  [principles](../../../steering/principles.md),
  [conventions](../../../steering/conventions.md) and
  [adopted stack](../../../steering/tech-stack.md).
- [Purchase design](../ticket-purchase/design.md) and its existing
  ticketing/payment model code.
- [Preliminary validation design](../ticket-validation/design.md).
- The current A-01 through A-14 Linear decision tickets, all in Backlog.

The original brief and requirements PDFs were not independently inspected in
this change. Requirement references below follow the repository and Linear
baseline; they are traceability, not evidence of teacher approval.
The adopted stack is a team technology decision. An unresolved assumption in
Linear stays unresolved even where the product/stack describes a working choice.

## Ownership and identifiers

Every authoritative entity has one owner. Same-owner references may become
foreign keys; cross-owner references are UUID values or event-fed projections.
Diagram relationships show domain cardinalities, not permission for database
joins across services. PostgreSQL is the adopted storage choice for the owning
backend services. Physical columns/indexes/migrations are deferred.

Entity IDs are UUIDs. Human codes are separate unique labels for lines, stops,
ticket types and validators. Service dates are local dates; timetable offsets
are interpreted in OPERATING_TIMEZONE. Actual instants are timezone-aware UTC.
How to represent overnight timetable offsets and ambiguous daylight-saving
times must be agreed before schedule implementation (A-01).

Proposed persistent records have UUID id and created_at/updated_at metadata.
Append-only records additionally carry occurred_at/decided_at as applicable;
updated_at never grants permission to alter their contents.
State snapshot version numbers are distinct from event schema versions.

| Authoritative owner | Entities / data | Other components may retain |
|---|---|---|
| core-backend | User, RoleAssignment, AccountProfile, Line, Stop, RoutePattern, PatternStop, Schedule, ScheduleVariant, ScheduledTrip, TripOccurrence, StopTime, TripOperationalState, Disruption, DisruptionScope, DisruptionChange, core StaffAudit | UUID references; versioned network/trip snapshots |
| ticketing-service | TicketType, Purchase, Ticket, TicketStateChange, Validator, ValidationAttempt, ticketing StaffAudit | Immutable ticket/payment references or minimized accepted-validation events |
| occupancy-service | BoardingObservation, BoardingAttribution, TripCapacity, OccupancyEstimate, HistoricalCrowding | Trip UUID and versioned core projection; accepted validation IDs |
| notification-service | Subscription, SubscriptionRevision, NotificationPreference, PreferenceRevision, Notification, DeliveryAttempt | User and target UUIDs; consent/contact data supplied by explicit interfaces, not DB access |
| payment-sim | SimulatedPayment | Opaque payment reference and recorded outcome in Purchase |
| Each publisher/consumer | Its own OutboxEvent / InboxEvent and processing metadata | No shared event tables |
| web and other simulators | No authoritative business data | Public cache or temporary request state only |

Validator ownership follows the preliminary validation design and needs team
confirmation; its stop belongs to core. TripCapacity is proposed as
occupancy-owned, consistent with the adopted stack and FR-054. No separate
vehicle entity is needed unless the team chooses vehicle-type defaults.

## 1. Network and schedules

Proposed model:

~~~mermaid
erDiagram
    LINE ||--o{ ROUTE_PATTERN : has
    ROUTE_PATTERN ||--|{ PATTERN_STOP : orders
    STOP ||--o{ PATTERN_STOP : appears_in
    LINE ||--o{ SCHEDULE : publishes
    SCHEDULE ||--|{ SCHEDULE_VARIANT : contains
    SCHEDULE_VARIANT ||--o{ SCHEDULED_TRIP : plans
    ROUTE_PATTERN ||--o{ SCHEDULED_TRIP : follows
    SCHEDULED_TRIP ||--|{ STOP_TIME : times
    PATTERN_STOP ||--o{ STOP_TIME : locates
    SCHEDULED_TRIP ||--o{ TRIP_OCCURRENCE : runs_on
    TRIP_OCCURRENCE ||--o| TRIP_OPERATIONAL_STATE : has
~~~

A draft may temporarily have zero children; cardinalities above describe a
publishable schedule/pattern, whose completeness must be validated.

| Entity | Main identifiers and proposed data | Relationships / invariants |
|---|---|---|
| Line | id, code, name, active status, version | Code unique; deactivation preserves past references |
| Stop | id, code, name, active status, version | Code unique; shared across lines/patterns |
| RoutePattern | id, line_id, direction label, revision, status | Proposed solution for ordered stops and direction; one line owns many patterns |
| PatternStop | id, pattern_id, stop_id, position | Unique (pattern_id, position), position positive; a stop may recur at another position |
| Schedule | id, line_id, revision, validity dates, publication status | Stable identity/revision keeps prior passenger-used schedules addressable |
| ScheduleVariant | id, schedule_id, selection conditions, precedence | A-01 gates condition rules, holidays and precedence |
| ScheduledTrip | id, variant_id, pattern_id, public identifier | Pattern's line matches schedule's line |
| StopTime | id, scheduled_trip_id, pattern_stop_id, arrival/departure offset | One time per trip and pattern occurrence; sequence nondecreasing, arrival <= departure |
| TripOccurrence | id, scheduled_trip_id, service_date, schedule_revision | Proposed dated run; unique logical run per trip and date, stable under retries |
| TripOperationalState | id, occurrence_id, state, delay, effective interval, version | Current materialized state derived from applicable disruptions; no editing the published baseline |

RoutePattern and TripOccurrence are design proposals, not extra passenger
features. They distinguish direction/stop occurrence and recurring timetable
templates from actual dated trips. The team must confirm these distinctions
before building schedule tables, trip subscriptions and occupancy references.

A departure board is a query over applicable trip occurrences and stop times,
with operational changes applied; it need not be an authoritative table.
Publishing validates referenced active entities and complete stop times.
Editing an already-used pattern/schedule creates a revision or preserves its
historical snapshot. It must not silently reinterpret previous operations.

## 2. Accounts, roles and disruptions

| Entity | Main data | Relationships / invariants |
|---|---|---|
| User | id, login identifier, recognized salted password hash, status | Core is identity authority; never put passwords in events |
| AccountProfile | id, user_id, contact data, minimal identity data | One profile per user; contact edits differ from protected identity edits (A-14) |
| RoleAssignment | id, user_id, role, validity/status | Passenger/staff authorization is server enforced; exact staff taxonomy A-07 |
| Disruption | id, type, description, effective_from/to, lifecycle, version, author UUID | Scope and period required; end > start when finite; source A-02 |
| DisruptionScope | id, disruption_id, line/pattern/stop/trip/occurrence target and optional period | Local references; target type and supplied reference must agree; trip-template versus dated-run scope explicit |
| DisruptionChange | id, disruption_id, author UUID, before/after snapshot or change record, occurred_at | Append-only; reason/correlation retained; no update/delete |
| StaffAudit | id, actor UUID, action, entity type/id, change metadata, occurred_at | Stored by the component executing the change, in the same local transaction |

A visitor is unauthenticated, not a User row. Staff and passengers need not be
separate identity tables: one identity plus roles avoids duplicate credentials.
Whether a person can hold multiple roles and how staff are provisioned remain
team decisions (A-07).

Account deletion is not cascading deletion of purchases, issued tickets or
history. The eventual deletion/anonymization workflow must resolve A-09/A-14
and avoid orphaning authorization references; this document sets no retention
duration and claims no privacy-policy approval.

Disruption target references live in core, where network/trips are owned.
Its effect is projected over the baseline: cancellation/diversion/delay must
not destroy original stop times. Overlapping disruptions need deterministic
precedence before implementation; do not assume last write wins.
The same transaction records staff changes, audit and local outbox intent.

## 3. Tickets, purchase and validation

~~~mermaid
erDiagram
    TICKET_TYPE ||--o{ PURCHASE : selected_for
    PURCHASE ||--o| TICKET : issues
    TICKET_TYPE ||--o{ TICKET : classifies
    TICKET ||--|{ TICKET_STATE_CHANGE : records
    VALIDATOR ||--o{ VALIDATION_ATTEMPT : submits
    TICKET o|--o{ VALIDATION_ATTEMPT : resolves
~~~

A purchase can have no ticket while pending/failed; a completed purchase has
exactly one. A valid issued ticket has an initial state-change record.
A validation attempt may reference no known ticket while retaining the
presented ticket UUID.

| Entity | Main data | Relationships / invariants |
|---|---|---|
| TicketType | id, code, name, description, integer price_cents, currency, terms, status | Nonnegative amount; explicit currency; validity terms versioned/defined before use (FR-048) |
| Purchase | id, passenger UUID, type_id, idempotency_key, fingerprint, immutable terms/price snapshot, payment reference, outcome/replay data | Unique (passenger UUID, operation key); same payload replays; changed payload conflicts; uncertain payment stays pending |
| Ticket | id, purchase_id, passenger UUID, type_id, terms_snapshot, issued_at, lifecycle data, version | Unique purchase_id; confirmed payment required; immutable issued terms; no cross-service FK to passenger |
| TicketStateChange | id, ticket_id, from/to state, reason, related attempt if any, occurred_at | Append-only; changes commit with ticket update |
| Validator | id, code, core stop UUID, credential binding, active status | Proposed ticketing owner; authenticated identity binds stop; credential issuing remains a feature decision |
| ValidationAttempt | id, validator_id, presented_ticket UUID, nullable ticket_id, stop UUID snapshot, idempotency_key, fingerprint, device_time, decided_at, result/reason, stored response | Unique (validator_id, operation key); rejected attempts retained; record and accepted effects atomic |
| SimulatedPayment | id, purchase UUID/idempotency reference, amount/currency, fingerprint, outcome | payment-sim owns it; no FK or distributed DB transaction to Purchase; no real card data |

A-05/A-08/A-13 gate final validator placement, payload and entitlement rules.
The provisional entrance model does not put a line_id or trip_id on a
ValidationAttempt: an entrance observation does not prove which bus was taken.
Server-authoritative decision time is a preliminary feature proposal, not an
approval recorded by MET-169.

Existing purchase code already has TicketType, Purchase, Ticket,
TicketStateChange, OutboxEvent and SimulatedPayment models. Their existence is
not proof of migrations, acceptance or production readiness.
The current Ticket model supports ISSUED only; the lifecycle below is a future
design, not a claim that validation states are implemented.

Important reconciliation before validation implementation:
- Purchase code calls the immutable field terms_snapshot; the preliminary
  validation design calls it terms. Keep one canonical immutable snapshot or
  explicitly migrate; do not create divergent sources.
- Existing state changes use reason; the validation proposal uses cause.
  Align their vocabulary and references in that feature's design.
- Preliminary validation clock, replay comparison and validator ownership
  decisions still need the feature's review. Do not resolve them by accident
  in these domain diagrams.

Strong consistency boundary: ticket lock, validity decision, attempt, ticket
update, state-change record and outbox intent share one ticketing transaction.
Accepted activity has a unique event ID; one retry never spends another
journey. Payment reconciliation remains purchase-owned and does not introduce
a transaction across the simulator and ticketing databases.

## 4. Subscriptions and notifications

| Entity | Main data | Relationships / invariants |
|---|---|---|
| Subscription | id, user UUID, target kind and UUID, lifecycle | One logical user-target subscription; line/stop/trip identity rules must be agreed |
| SubscriptionRevision | id, subscription_id, target snapshot, effective_from/to, status | Versioned effective history supports event-time matching; intervals do not overlap |
| NotificationPreference | id, user UUID, channel configuration, current revision | Channel scope depends on A-06; contact data obtained through explicit core interface |
| PreferenceRevision | id, preference_id, effective_from/to, consent/channel snapshot | Event-time preference reconstruction; future contact edits do not rewrite old attempts |
| Notification | id, triggering event UUID, user UUID, channel, content snapshot, event time, read/status metadata | Unique (event_id, user UUID, channel), including overlapping subscription matches |
| DeliveryAttempt | id, notification_id, attempt number, destination reference/snapshot, attempted_at, outcome, retry time | One notification to many recorded attempts; no claim of exactly-once SMTP delivery |

One user has many subscriptions; each subscription has revision history.
One triggering event can create many recipient notifications; a notification
has zero or more delivery attempts. Inbox read/unread state is local to the
recipient. Keep only the contact data necessary for delivery and approved
history retention; do not copy complete core profiles.

The meaning of a trip subscription (template or dated occurrence) needs team
agreement. Model target kinds explicitly once agreed.
Processing delayed events uses the preferences/subscriptions valid at the
event's occurrence time (FR-068), not whichever values are current on receipt.
Delivery-attempt history may append while notification delivery/read status
changes. A-06 and A-09 gate final channel and retention fields.

## 5. Boarding and occupancy

| Entity | Main data | Relationships / invariants |
|---|---|---|
| BoardingObservation | id, accepted validation/event UUID, core stop UUID, observed/received times | Unique accepted activity ID; estimates never add rejected attempts or retries |
| BoardingAttribution | id, observation_id, trip occurrence UUID, rule version, estimated contribution | Proposed only; cardinality/weights and conservation rule await A-03 |
| TripCapacity | id, trip occurrence UUID or approved template reference, capacity, effective period/version | Positive capacity; one authoritative applicable value per trip; default source requires review |
| OccupancyEstimate | id, trip occurrence UUID, as_of, rule/data version, estimated value, completeness/staleness | Derived and explicitly labelled estimate; no alighting data means no measured onboard occupancy |
| HistoricalCrowding | id, approved grouping keys, window, rule version, coarse level, computed_at | Derived aggregate; public visibility/levels await A-11 and A-03 |

One observation may contribute to several candidate trips under a future
approved attribution rule. Do not infer a one-to-one observation/trip relation
or choose equal shares here. Occupancy owns attribution, core owns trip
identity, ticketing owns validation truth.
Replaying an accepted activity does not contribute twice even if events arrive
out of order. Snapshot entity versions only prevent stale state replacement;
they must not discard distinct accepted validations.

Capacity changes do not overwrite historical estimates without a recorded
recomputation policy. These records are an analytical design surface, not
implemented statistical truth or a source of per-line validation statistics.

## 6. Event records and stable versus operational data

Each publisher owns its OutboxEvent: event_id unique, schema type/version,
entity version where applicable, occurred_at, correlation ID, payload and
publication status. Business state and event intent commit together.
Each consumer owns InboxEvent: event_id unique, processing metadata committed
with the consumer's local effects. These are per-service tables; no shared DB.

The broker transports events and owns no canonical business entities.
Delivery is at least once. An inbox duplicate is harmless; a failed transaction
must not leave an inbox mark that prevents a correct retry.
Detailed wire schemas, interactions, retries and failure models belong to
MET-88 / MET-170 and the appropriate feature, not this document.

| Stable/reference data | Operational/history data | Preservation rule |
|---|---|---|
| Line, Stop, RoutePattern | Pattern/schedule revisions and used references | Deactivate or revision; preserve historical meaning |
| Schedule and variant definitions | TripOccurrence and disruption effects | Keep published baseline separate from actual dated state |
| TicketType | Purchase, Ticket, ValidationAttempt | Issued terms immutable; retire types instead of rewriting tickets |
| Identity and roles | Audit, subscription/preference history | References stay interpretable under approved anonymization/retention |
| Capacity/rule configuration | Observations, attributions, estimates | Store rule/version/time and distinguish observations from derived results |

## Lifecycle summary

These are proposed semantic states, not Django enums. Terminal definitions and
the exact allowed transition guards are feature-level decisions.

| Entity | Proposed lifecycle / transition constraints |
|---|---|
| Line/Stop | active -> inactive; reactivation, if allowed, preserves identity/history |
| Pattern/Schedule | draft -> published -> superseded/retired; published used revisions remain addressable |
| TripOccurrence | scheduled -> completed/cancelled; delay/diversion are effective operational states, not destructive timetable edits |
| Disruption | planned -> active -> closed, or planned -> cancelled; effective time differs from record creation time |
| User | active -> disabled/deletion-pending -> approved anonymized/retained outcome; A-09/A-14 unresolved |
| TicketType | active -> retired; issued snapshots unchanged |
| Purchase | pending -> completed or failed; uncertain provider outcomes remain pending for reconciliation |
| Ticket | issued -> active -> used-up/expired; expiration/cancellation rules and eligibility await feature review; transitions append history |
| Validator | active -> inactive; historical attempts retain stop/identity snapshot |
| Subscription | active -> cancelled; effective revisions retained under A-09 |
| Notification | created -> delivery pending -> delivered/retryable-failure; read/unread independent; A-06 decides channels |
| Outbox | pending -> published only after broker confirmation without routing return; retry preserves event ID |
| Observation/history | append-only activity; derived estimates may be superseded with lineage |

## Requirement consistency and acceptance boundaries

| Requirements | Model evidence | Relevant design caveat |
|---|---|---|
| FR-001–009, FR-070–075 | Network/schedule entities, ordered occurrences and revisions | Variant/calendar semantics A-01; no endpoint implementation |
| FR-010–014, FR-090–095 | Operational state, scopes and append-only disruption changes | Source A-02; overlap precedence unresolved |
| FR-020–024, FR-100–102 | Identity, profile and role ownership, UUID privacy boundaries | A-07/A-14, deletion retention A-09 |
| FR-030–048, FR-080–084 | Ticket terms, purchase/payment references, attempts, lifecycle history | A-04/A-05/A-08/A-12/A-13 and validation design reconciliation |
| FR-050–056 | Observations versus attribution/capacity/estimates | A-03/A-11; no measured occupancy claim |
| FR-060–069 | Subscription/preference revisions, deduplicated notifications and attempts | A-06, A-09; event-time matching and uncertain SMTP |
| FR-103, FR-105 | Stable/operational separation and preservation rules | A-09 remains unapproved; no retention duration invented |
| NFR-004/005/032 | Single authoritative owner and UUID boundaries | Full architecture justification is MET-87; this supplies entity ownership |
| NFR-013–015/030/031 | Local consistency, unique replay keys, event/derived-state distinctions | Transport/interaction verification is later work |
| NFR-033/050/051/056/057 | UTC metadata, role boundaries, hash-only credentials, minimized data/audit | No implemented security/privacy compliance claim |

See [assumptions.md](assumptions.md) for all A-01–A-14 decisions and
[review.md](review.md) for acceptance evidence and remaining review.
