# Requirements — Ticket Purchase with Simulated Payment

**Status:** DRAFT, iteration 2. Decisions N-01 to N-13 are approved by the team. Everything tagged **[D]** is new in this iteration and still needs team review.
**Feature folder:** `.ai/sdd/specs/ticket-purchase/`
**Owning component:** `apps/ticketing-service` (with `simulators/payment-sim`)

## 0. How to read this document

| Tag | Meaning |
|---|---|
| **[S]** | Stated in the official project statement (v1.0, 2026-09-29). Quoted. |
| **[V]** | From the team's requirements specification **v0.2** (2026-10-01). IDs are verified against that document. In v0.2, "(A)" marks a team assumption, not a statement requirement. |
| **[P]** | From the PL5 steering files (`product.md`, `tech-stack.md`, `conventions.md`, `principles.md`). A team decision. |
| **[N]** | New decision **approved by the team** (N-01 to N-13, §5.1). |
| **[R]** | New decision **not approved**; to be reworked in the next iteration. None at present. |
| **[D]** | New proposal in this iteration, **awaiting review** (§5.2). Numbering continues from the original sequence so no ID is reused. |
| **[A]** | Assumption, unverified. |

**IDs.** `PUR-FR-xx` / `PUR-NFR-xx` are feature-level refinements. Each maps to real v0.2 IDs in the "Spec v0.2" column. Per `conventions.md`, tests carry `@pytest.mark.req("<v0.2 ID>")` so the project-wide traceability report works; the `PUR-*` ID is the feature-level handle used in this folder.
**Priority** (Pri) is inherited from the linked v0.2 requirement (M/S/C). "—" means there is no v0.2 counterpart (team decision only).

### Changes since the previous draft
1. D-01…D-13 are approved and renamed **N-01…N-13**.
2. Spec v0.2 is now available: every cross-reference is verified, the "unverified" caveat is removed, and priorities are added.
3. v0.2 **FR-036** (purchase confirmation, including asynchronous completion) and **NFR-031** (cross-component delay must be bounded and documented) were missing from the previous draft. They add **PUR-FR-18**, **PUR-NFR-12**, **D-14** and **OQ-10**.
4. Finding AMB-08 was wrong and is corrected: v0.2 does require a purchase confirmation. Only its *delivery* is outside this feature.
5. OQ-04 (ID mapping) and OQ-07 (staff purchases, now N-08) are closed. Health/metrics and server-side validation requirements are added (PUR-NFR-11, 13).

## 1. Feature description

> As a **passenger**, I want to buy a ticket of a chosen type, paying with a simulated payment, so that the ticket is added to my account — and I want a retry, a timeout or a component failure never to charge me twice, give me two tickets, or charge me and give me nothing.

### 1.1 Why this feature
It is bounded (one write path, one simulator, one event) and it concentrates the cross-component concerns the statement asks for (idempotency, retries, consistency across components, partial failure). v0.2 section 6 describes this exact interaction: "web app → ticketing service (sync, with idempotency key) → payment simulator", followed by the `TicketPurchased` event.

### 1.2 In scope
1. List purchasable (active) ticket types, read only [N-01] (v0.2 FR-031).
2. `POST` a purchase of **one ticket of one type** by an authenticated passenger, with simulated payment (FR-032, FR-037).
3. `GET` the status of one's own purchase, which is also how an asynchronously completed purchase is confirmed (FR-036).
4. `payment-sim`: an idempotent simulated payment API with deterministic failure modes for tests.
5. A reconciliation process that drives uncertain (`PENDING`) purchases to a terminal state.
6. Publishing `TicketPurchased` through the transactional outbox, and its schema.

### 1.3 Out of scope (explicitly)
| Item | Where it belongs |
|---|---|
| Staff maintenance of ticket types (ticket types are seeded for this feature) | v0.2 FR-080 |
| Listing a passenger's tickets and validation history | v0.2 FR-034 (a **Must** that depends on tickets created here; its feature must read the fields defined in design §3) |
| Ticket validation, activation and the lifecycle after `ISSUED` | v0.2 FR-040…FR-048, FR-035 |
| Delivering the confirmation by notification (in-app/e-mail) | notification feature; this feature only publishes the event |
| Occupancy | not needed to complete a purchase |
| Web UI screens (API-first slice; deferred task T-30) | — |
| Refunds, transfers | v0.2 A-12 |
| Quantity > 1 | N-02 |
| Real payment processing | v0.2 A-04 |
| Account deletion vs. retained purchases | accounts feature (v0.2 FR-023); see AMB-12 |

## 2. Sources

### 2.1 Project statement passages [S]
| # | Passage (short quotation) | Location | Used for |
|---|---|---|---|
| S-1 | "Ticket types may differ in their price, period of validity, conditions of use, or number of permitted journeys." | Technical Description, tickets paragraph | A ticket carries the type's price and terms |
| S-2 | "Passengers should be able to acquire tickets and consult the tickets associated with their account." | same | Purchase needs an account; ticket belongs to it |
| S-3 | "The system should also handle communication failures without causing unintended effects, such as issuing the same ticket…" | failures paragraph | Idempotent purchase; no duplicate ticket |
| S-4 | "a failure of the notification functionality should not prevent passengers from … using other unrelated functionality" | same | Purchase must not depend on notification |
| S-5 | "Handling of communication failures, timeouts, and temporary component unavailability" | Communication and Integration | Payment-sim timeouts and failures |
| S-6 | "Appropriate handling of retries and duplicate messages or operations" | same | Idempotency keys, outbox |
| S-7 | "Appropriate mechanisms for maintaining consistency when an operation involves multiple components" | same | Purchase spans ticketing and payment-sim |
| S-8 | "Synchronous communication through appropriate APIs; Asynchronous/event-based communication for appropriate operations" | same | REST to payment-sim; event for `TicketPurchased` |
| S-9 | "Historical information may be relevant for understanding previous system activity" | lifecycles paragraph | State changes appended, not overwritten |

**Finding:** the statement never mentions *payment*, pricing at purchase, or refunds. v0.2 records the simulated payment as a **team assumption** (FR-037, A-04, both marked (A)); "no refunds" is A-12. They are not stakeholder requirements.

### 2.2 Requirements specification v0.2 used by this feature [V]
| v0.2 ID | Pri | Content (abridged) | Used by |
|---|---|---|---|
| FR-030 | M | Multiple ticket types differing in price, validity, conditions, journeys | PUR-FR-06 |
| FR-031 | M | Show ticket types available for purchase, with price and conditions | PUR-FR-01 |
| FR-032 | M | A passenger can acquire a ticket of an available type | PUR-FR-02 |
| FR-033 | M | Ticket issued at most once per purchase request, even if retried or duplicated | PUR-FR-02…05, 09, NFR-01 |
| FR-035 | M | Ticket has an explicit lifecycle state; state changes recorded | PUR-FR-09 |
| FR-036 | S | Purchase produces a confirmation, including when payment or issue completes asynchronously | PUR-FR-11, 13, 15, 18 |
| FR-037 | S | A payment step; simulated provider acceptable (A-04) | PUR-FR-08, 10 |
| FR-044 | M | A successful validation may start the validity period | N-03 (validity start is not decided at purchase) |
| FR-048 | S | Validity rules per ticket type in data/configuration | `terms` snapshot is copied opaquely |
| FR-081 | M | Changing a ticket type does not alter issued tickets | PUR-FR-06, 17 |
| FR-100…102 | M | Roles enforced; passenger reaches only their own data | PUR-FR-13, 14 |
| FR-103 | M | Historical data retained | no hard deletes |
| NFR-004, 032 | M | No shared DB access; single owning component | design §3 |
| NFR-006 | M | Machine-readable, versioned contracts | PUR-FR-15, NFR-06 |
| NFR-010 | M | Sync where an answer is needed, async where appropriate | PUR-FR-15 |
| NFR-012 | M | Every inter-component call has a timeout and failure behaviour | PUR-FR-11, NFR-03 |
| NFR-013 | M | Retry-safe operations; idempotency keys for ticket purchase | PUR-FR-03…05, 16, NFR-01 |
| NFR-014 / 016 | M / S | Consumers tolerate duplicates/reordering; dead-letter | event contract |
| NFR-015 | M | Cross-component operations use a consistency mechanism, documented | PUR-FR-09, 11, 12 |
| NFR-020 / 021 | M | One component's failure does not take the system down; events not lost | PUR-NFR-02 |
| NFR-022 | M | No duplicate ticket/validation/notification from communication failures | PUR-FR-12, NFR-01 |
| NFR-030 | M | Strong consistency of ticket state within the owning component | PUR-FR-09 |
| NFR-031 | M | Cross-component data may be eventually consistent with a **documented, bounded** delay | PUR-NFR-12 |
| NFR-050, 053 | M / S | Authentication and role authorization; authenticated inter-component calls | PUR-FR-14, NFR-03 |
| NFR-055, 056, 063 | M / M / S | Server-side validation; data protection; understandable errors | PUR-NFR-13, 05, 04 |
| NFR-070…072 | M | Correlation ids; health and metrics; failure detection | PUR-NFR-05, 11 |
| NFR-081, 083, 085, 087 | M | Real-dependency integration tests; contract tests; failure tests; traceability | PUR-NFR-06, 08, tasks |
| NFR-040, 041, 043 | S | Latency targets for reads, validation, and load peaks. **None for purchase** | PUR-NFR-10 |

v0.2 assumptions this feature relies on: A-04 (simulated payment), A-07 (one staff role), A-08 (tickets network-wide unless a type says otherwise), A-12 (no refunds or transfers).

## 3. Actors, inputs, outputs, dependencies

| Actor / dependency | Role in this feature |
|---|---|
| Passenger (authenticated, role `passenger`) | Submits purchase, reads status |
| Visitor | May list ticket types only [N-01] |
| `ticketing-service` | Owns ticket types, purchases, tickets, state changes, outbox (v0.2 section 6) |
| `payment-sim` | Approves/declines payments; idempotent by key |
| `core-backend` | Owns identity; ticketing verifies JWTs with its public key (JWKS) and never reads its DB |
| RabbitMQ `metro.events` + outbox relay | Carries `TicketPurchased`; **not** on the purchase's critical path |
| Reconciler (system actor) | Finishes `PENDING` purchases |
| Staff | Not an actor of this feature; cannot purchase [N-08] |

**Inputs (purchase):** `Authorization: Bearer <JWT>`, `Idempotency-Key` (UUID), `X-Correlation-Id` (optional), body `{ ticketTypeId, expectedPriceCents, paymentMethodToken }`.
**Outputs:** purchase resource (`COMPLETED` / `PENDING` / `FAILED`) with the issued ticket id on success, the `TicketPurchased` event, structured logs and metrics.

## 4. Requirements

### 4.1 Functional

| ID | Requirement | Pri | Source | Spec v0.2 |
|---|---|---|---|---|
| PUR-FR-01 | The system shall list ticket types that are currently active, each with id, name, `priceCents`, `currency` and a human-readable description of its conditions. | M | V, N-01 | FR-031 |
| PUR-FR-02 | An authenticated passenger shall be able to purchase exactly one ticket of one active ticket type per purchase request. | M | V, N-02, S-2 | FR-032, FR-033 |
| PUR-FR-03 | `POST /purchases` shall require an `Idempotency-Key` (UUID). A missing or malformed key shall be rejected with 400 before any state is created. | M | V, P | FR-033, NFR-013 |
| PUR-FR-04 | The same key and payload from the same passenger shall replay the stored terminal response, or the current pending state; no second purchase, payment or ticket shall result. | M | V, S-3, S-6 | FR-033, NFR-013, NFR-022 |
| PUR-FR-05 | The same key with a different payload shall return 409 `IDEMPOTENCY_KEY_REUSED` and change nothing. Keys are scoped per caller and operation. | M | V, P | NFR-013 |
| PUR-FR-06 | At purchase creation the system shall snapshot the ticket type's price, currency and terms into the purchase. Later changes to the type shall not alter what is charged or issued. | M | V, S-1, P | FR-030, FR-081 |
| PUR-FR-07 | If `expectedPriceCents` differs from the type's current price, the system shall reject with 422 `PRICE_CHANGED` and create nothing. | — | N-04, P (principle 9) | — |
| PUR-FR-08 | The system shall request payment from `payment-sim` using the purchase id as the payment idempotency key and the snapshot price and currency. | S | V, N-05 | FR-037 |
| PUR-FR-09 | On payment approval the system shall, in **one database transaction**, create one ticket (copy of the snapshot terms), append a ticket state-change record (`ISSUED`), mark the purchase `COMPLETED` with its stored response, and write one `TicketPurchased` outbox event. | M | V, S-3, S-7, P | FR-033, FR-035, NFR-015, NFR-030 |
| PUR-FR-10 | On payment decline the purchase shall become `FAILED` (terminal): no ticket, no event. The same key replays the same 422 `PAYMENT_DECLINED`; a new key starts a new purchase. | S | V, N-06 | FR-037 |
| PUR-FR-11 | If the payment outcome is not definitively known (timeout, connection loss after send, 5xx, sim unavailable), the purchase shall stay `PENDING`, no ticket shall be issued, and the response shall indicate pending state (HTTP 202; see OQ-01) — never an invented success or failure. | M | V, S-5, N-06 | NFR-012, NFR-015, FR-036 |
| PUR-FR-12 | A reconciliation process shall repeatedly resolve `PENDING` purchases by replaying the payment request with the **same** key until an approval or decline is obtained, then finalize as in PUR-FR-09/10. A retry or reconciliation shall never start a second payment or issue a second ticket. | M | V, S-7, P (principle 3) | NFR-015, NFR-022 |
| PUR-FR-13 | A passenger shall be able to read the status of their own purchase (`GET /purchases/{id}`). A purchase of another user shall appear as 404. | M | V, P (principle 6) | FR-102, NFR-050, FR-036 |
| PUR-FR-14 | Only role `passenger` may create purchases; other roles get 403. Role checks run before business logic. | M | V, N-08 | FR-100, FR-102, NFR-050 |
| PUR-FR-15 | The system shall publish `TicketPurchased` (routing key `ticketing.ticket.purchased`) through the outbox, with the standard envelope, the schema committed in `contracts/events`, and no personal data beyond UUIDs. | M | V, S-8, P | NFR-006, NFR-010, NFR-013, FR-036 |
| PUR-FR-16 | Pre-payment rejections (unknown/inactive type, `PRICE_CHANGED`, validation errors) shall not create a purchase and shall not consume the idempotency key. An existing key shall be resolved (replay/conflict) **before** these checks are re-run. | M | N-07 | NFR-013 |
| PUR-FR-17 | A type deactivated after a purchase was created shall not prevent that purchase from completing once payment is confirmed. | M | V, P (principles 3, 7) | FR-081 |
| PUR-FR-18 | The passenger shall receive confirmation of the purchase outcome: in the immediate response, and, when completion is asynchronous, through `GET /purchases/{id}` and the `TicketPurchased` event emitted on completion. Delivering a notification from that event is out of scope. | S | V (section 6 "Main interactions") | FR-036 |

### 4.2 Non-functional and constraints

| ID | Requirement | Pri | Source | Spec v0.2 |
|---|---|---|---|---|
| PUR-NFR-01 | Under N ≥ 10 concurrent identical requests, exactly one purchase, one payment record at `payment-sim` and one ticket shall exist. Uniqueness is enforced by database constraints, not only application code. | M | V, S-3, P (principle 2) | FR-033, NFR-013, NFR-022, NFR-030 |
| PUR-NFR-02 | Purchase shall not depend on notification, occupancy or RabbitMQ availability. With any of them down, a purchase completes and its event stays pending in the outbox until published. | M | V, S-4, P (principle 5) | NFR-020, NFR-021 |
| PUR-NFR-03 | Calls to `payment-sim` use the shared HTTP client wrapper: connect timeout 1 s, read 3 s, correlation header, service token. No bare `requests`. The request shall never hang. | M | V, S-5, P | NFR-012, NFR-053 |
| PUR-NFR-04 | All errors use the single error shape `{error:{code,message,correlationId}}`; messages never expose internals; unexpected failures log the correlation id and return a generic message. | S | V, P | NFR-063 |
| PUR-NFR-05 | Logs are structured (`structlog`, snake_case events) with `correlation_id`; payment tokens, JWTs and personal data are never logged. | M | V, P | NFR-056, NFR-070 |
| PUR-NFR-06 | The committed OpenAPI file and the event JSON Schema match the generated ones; the pipeline fails on drift. | M | V, P | NFR-006, NFR-083 |
| PUR-NFR-07 | Money is an integer in minor units plus a currency code; never float. | — | P | — |
| PUR-NFR-08 | Every test verifying a requirement carries `@pytest.mark.req("<v0.2 ID>")`. | M | V, P | NFR-087 |
| PUR-NFR-09 | No real payment data is collected: the payment method is an opaque simulated token. | — | V (A-04), P | — |
| PUR-NFR-10 | **No latency or throughput target is asserted** for purchase. v0.2 gives targets only for reads (NFR-040), validation (NFR-041) and validation/consultation peaks (NFR-043). | — | — | open (OQ-08) |
| PUR-NFR-11 | `ticketing-service` and `payment-sim` expose `/health/live` and `/health/ready` and metrics. Ticketing exposes the number of `PENDING` purchases and the age of the oldest, so a stuck reconciliation can be alerted on. | M | V, P, D-15 | NFR-071, NFR-072 |
| PUR-NFR-12 | The delay between a `PENDING` purchase and its terminal state, when `payment-sim` is reachable, shall be bounded by configuration and the bound documented. Proposed bound: resolution within 5 minutes after `payment-sim` becomes reachable (the reconciler's backoff cap). | M | V, D-14 | NFR-031 |
| PUR-NFR-13 | All request data is validated server-side by serializers (types, UUID formats, `paymentMethodToken` format and length), with no trust in client-supplied identity. | M | V | NFR-055 |

## 5. Decisions

### 5.1 Approved by the team [N]
N-12 and N-13 are approved in principle; the numeric values they leave open are tracked in OQ-05 and OQ-06.

| ID | Decision | Justification | Alternative considered | Spec v0.2 evidence |
|---|---|---|---|---|
| N-01 | `GET ticket-types` is public (`AllowAny`) and returns only active types. | A passenger must see price before buying; prices are not sensitive. | Passenger-only | FR-031 does not require login |
| N-02 | One purchase = one ticket (quantity 1). | Keeps "confirmed payment ends in exactly one ticket" checkable. | Quantity field (N tickets per payment, harder atomicity) | Spec silent |
| N-03 | A ticket is created in status `ISSUED`. When validity starts (at purchase, at first validation, or on a date) is **not decided here**; the snapshot stores the type's rules, not absolute dates. | Belongs to the validation feature. | Activate at purchase (invents a rule) | FR-044 lists "start the validity period" as a possible effect of validation; FR-035 distinguishes issued/active |
| N-04 | The client sends `expectedPriceCents`; mismatch → 422 `PRICE_CHANGED`. | Principle 9: never silently charge or show wrong data. | Charge the current price and return it | Spec silent |
| N-05 | Payment idempotency key = purchase id; `payment-sim` is idempotent by key (same key and payload replays; different payload → 409). | Retrying with the same key *is* the reconciliation mechanism. | Separate status lookup | FR-037, NFR-013 |
| N-06 | Only an explicit `APPROVED` or `DECLINED` from `payment-sim` is definitive; everything else is uncertain. | A timeout or 5xx may hide a charge; failing it could charge without a ticket. | Treat 5xx as failure | NFR-015, NFR-022 |
| N-07 | The idempotency lookup happens before business checks; pre-payment rejections do not store the key. | A replay must still work after a type is retired. | Check first | NFR-013 |
| N-08 | Only `passenger` can purchase; staff-only accounts get 403. | Role separation; staff purchasing is not stated. | Allow staff | FR-100, A-07 |
| N-09 | In the request: **one** payment attempt; retries are done by the reconciler. | Bounded latency; one retry path to test. | 3 in-request retries | NFR-012 |
| N-10 | The idempotency record lives on the purchase row and **never expires** (purchases are never hard-deleted). | Avoids a window where an old key silently creates a second purchase. | 24 h TTL | FR-103 |
| N-11 | The payment method is an opaque token; `payment-sim` maps reserved tokens to outcomes (`sim_approve`, `sim_decline`, `sim_slow`, `sim_error`, `sim_lose_response`). | Deterministic failure injection. | Random failures | NFR-025, NFR-085 |
| N-12 | A `PENDING` purchase is never auto-failed; after a threshold it raises an alert. | An auto-fail could contradict a real approval. | Auto-fail after a timeout | NFR-015 |
| N-13 | `ticketing-service` caches core-backend's public key (JWKS) with a TTL and keeps verifying with the cached key if core-backend is briefly unreachable. | A purchase should not fail because of an unrelated component's outage (S-4). | Fetch JWKS on every request | NFR-020 |

### 5.2 Proposed in this iteration, awaiting review [D]
| ID | Proposal | Justification | Alternative |
|---|---|---|---|
| D-14 | Document the `PENDING` resolution bound (PUR-NFR-12) and set it, as a configurable value, to 5 minutes after `payment-sim` becomes reachable. | v0.2 NFR-031 requires cross-component delays to be bounded and documented; 5 min matches the backoff cap in design §6.3. The number is a proposal, like v0.2's own proposed targets. | A tighter bound (e.g. 60 s) with a smaller backoff cap |
| D-15 | Expose `PENDING` count and oldest age as metrics (PUR-NFR-11) and base the OQ-05 alert on them. | NFR-071/072 require metrics and detection of failures; N-12 relies on an alert. | Alert from logs only |

### 5.3 Not approved [R]
None.

## 6. Ambiguities, inconsistencies and gaps

| ID | Finding | Handling |
|---|---|---|
| AMB-01 | The statement does not mention payment. v0.2 records it as team assumption A-04 / FR-037. | Treated as a team decision, not a stakeholder requirement (§2.1). |
| AMB-02 | *(Resolved)* Steering files cite FR/NFR IDs from v0.2. | v0.2 received; all IDs cited in the steering files that this feature uses were checked and match their meaning (FR-033, FR-035, FR-081, NFR-012/013/015, NFR-020/021, NFR-056, NFR-063, NFR-070). |
| AMB-03 | `AGENTS.md` is empty (0 bytes). `tech-stack.md` and `tech-stack_1.md` are byte-identical. | Task T-01. |
| AMB-04 | `conventions.md` says "when a dependency is down, return 503", but PUR-FR-11 returns 202 `PENDING` when `payment-sim` is unreachable, because a purchase already exists. | **Conflict → OQ-01.** Recommendation: 202 once a purchase is recorded; 503 only when nothing was recorded. |
| AMB-05 | `payment-sim` has no route namespace in conventions' service list. | OQ-03. Proposed `/api/payment-sim/v1/payments`. |
| AMB-06 | tech-stack.md draws `payment-sim` without storage; an idempotent simulator that forgets keys on restart would double-"charge". | OQ-03. Proposed SQLite on a named volume. |
| AMB-07 | A reconciler is a new deployment role not listed in tech-stack.md. | OQ-02. |
| AMB-08 | *(Corrected)* v0.2 FR-036 and section 6 do require a purchase confirmation, sent by the notification service from `TicketPurchased`. The earlier claim that no document required it was wrong. | This feature provides the confirmation data (response, status endpoint, event: PUR-FR-18). Delivery is the notification feature's job. |
| AMB-09 | "Redeliver the same event, assert one effect" needs a consumer; this feature has none. | Deferred to the notification feature (T-31); here the relay's duplicate publication with the same `eventId` is tested. |
| AMB-10 | JWKS unreachable and cache cold would make a purchase fail because of an unrelated component. | N-13; remaining values in OQ-06. |
| AMB-11 | When validity starts is undefined. | N-03; evidence in FR-044. Blocks validation, not purchase. |
| AMB-12 | v0.2 FR-023 allows account deletion, while FR-103 and principle 7 retain history and forbid hard deletion of business data. | Out of scope. This feature stores only the passenger UUID. OQ-11. |
| AMB-13 | FR-036 is a *Should* and FR-037 a *Should*, while FR-032 (acquire a ticket) is a *Must*. The Must can in principle be met without payment. | Payment is kept because product.md and A-04 make it part of the purchase. Recorded so the team knowingly relies on a Should-level step. |

## 7. Open questions (⛔ = blocking)

| ID | Question | Blocks |
|---|---|---|
| OQ-01 ⛔ | 202 `PENDING` vs 503 for payment-sim failure: which does the team adopt, and which document is updated (conventions.md or this spec)? | API contract task | **priorize other documents to this one**
| OQ-02 ⛔ | Add a `reconciler` deployment role to ticketing (update tech-stack.md), or reconcile lazily on read? Lazy-only cannot satisfy principle 3 if the client never returns. | Reconciler task, deployment | **
| OQ-03 ⛔ | `payment-sim` route namespace and persistence mechanism. | payment-sim tasks |
| OQ-05 | Threshold for alerting on stuck `PENDING` purchases (with D-15); any manual resolution procedure? | Alert rule only |
| OQ-06 | JWKS cache TTL and cold-cache behaviour (N-13). | Auth task |
| OQ-08 | Purchase latency target and test workload (none in v0.2). | Performance task (not planned) |
| OQ-09 | Currency policy: one seeded currency or several? v0.2 is silent. This spec assumes one currency per ticket type, EUR seeded. | Seed data |
| OQ-10 | Confirm D-14: the numeric bound on `PENDING` resolution (proposed 5 min). | Reconciler configuration, AS-06/07 timing |
| OQ-11 | Policy for retained purchases and tickets when an account is deleted (FR-023 vs FR-103). Owned by the accounts feature. | Not blocking |

**Closed:** OQ-04 (ID mapping, resolved by v0.2). OQ-07 (staff purchases, decided in N-08).

## 8. Acceptance scenarios

Format: Given / When / Then with observable outcomes. "Counts" refer to rows in `purchases`, `tickets`, `ticket_state_changes`, `outbox_event` and payments recorded at `payment-sim`. "Covers" uses `PUR-` IDs without the prefix.

| ID | Covers | Scenario |
|---|---|---|
| AS-01 | FR-02, 08, 09, 15 | **Happy path.** Given an active type (price 150 c, EUR) and a passenger, when they POST a purchase with a new key, `expectedPriceCents=150`, token `sim_approve`, then 201 `COMPLETED` with a `ticketId`; counts: purchases 1, tickets 1 (terms equal the snapshot), state changes 1 (`ISSUED`), outbox 1 `TicketPurchased` (pending), sim payments 1. |
| AS-02 | FR-04 | **Replay.** Given AS-01 completed, when the identical request is sent again, then the identical status and body are returned and all counts are unchanged. |
| AS-03 | FR-05 | **Key reuse.** Given AS-01 completed, when the same key is sent with a different `ticketTypeId`, then 409 `IDEMPOTENCY_KEY_REUSED` and counts are unchanged. |
| AS-04 | NFR-01, FR-04 | **Concurrency.** When 10 identical requests (same key) are sent simultaneously, then purchases 1, tickets 1, sim payments 1; every response is 201 or 202 carrying the same purchase id; no 5xx. |
| AS-05 | FR-10 | **Decline.** With token `sim_decline`, then 422 `PAYMENT_DECLINED`, purchase `FAILED`, tickets 0, outbox 0. Replaying the key returns the same 422. A new key with `sim_approve` succeeds independently. |
| AS-06 | FR-11, 12, NFR-12 | **Timeout.** With `sim_slow` (delay > 3 s read timeout), then 202 `PENDING`, tickets 0. Once the reconciler runs, the purchase is `COMPLETED` within the configured bound, tickets 1, sim payments 1. |
| AS-07 | FR-11, 12, 09 | **Approved but response lost.** With `sim_lose_response` (sim records the approval, drops the connection), then 202 `PENDING`; after reconciliation, tickets 1 and sim payments 1 (no second charge). |
| AS-08 | FR-09, 12 | **Crash between payment and issuance.** Kill ticketing after the approval is received but before the finalization transaction commits; on restart the reconciler completes it: tickets 1, outbox 1, sim payments 1. |
| AS-09 | NFR-02, FR-11 | **payment-sim down.** With `payment-sim` stopped, a purchase returns the pending outcome, no ticket; unrelated endpoints remain available; after restart and reconciliation → `COMPLETED`, tickets 1. *(Status code pending OQ-01.)* |
| AS-10 | FR-16 | **Inactive type.** For an inactive type, 422 `TICKET_TYPE_NOT_AVAILABLE`; for an unknown id, 404 `TICKET_TYPE_NOT_FOUND`; purchases 0; the same key can later be used for a valid request. |
| AS-11 | FR-07 | **Price changed.** If the type's price changed after listing, then 422 `PRICE_CHANGED`, purchases 0, sim payments 0. |
| AS-12 | FR-06, 17 | **Retired mid-flight.** Given a `PENDING` purchase (AS-06), when the type is deactivated and its price changed, then after reconciliation the ticket is issued with the **original** snapshot terms and the original price was the amount charged. |
| AS-13 | FR-16, 04 | **Replay after retirement.** Given AS-01 completed and the type since deactivated, replaying the same request returns the original 201, not 422. |
| AS-14 | FR-03 | **Missing/malformed key.** No header, or the value `not-a-uuid` → 400 `IDEMPOTENCY_KEY_REQUIRED`; no rows created. |
| AS-15 | FR-13, 14 | **Authorization.** No token → 401. A staff-only token → 403 (N-08). Passenger B reading passenger A's purchase → 404. |
| AS-16 | NFR-02, FR-15 | **Broker down.** With RabbitMQ stopped, a purchase returns 201; the outbox row stays pending; after the broker returns the relay publishes it with the original `eventId`; a crash between publish and "mark published" yields a duplicate publication with the same `eventId`. |
| AS-17 | FR-15, NFR-06 | **Event contract.** The published message validates against the `contracts/events` schema, carries the envelope fields, `correlationId` equal to the request's, and no personal data. |
| AS-18 | NFR-04, 05 | **Errors and logs.** Every error response matches the shape and echoes `X-Correlation-Id`; logs contain `correlation_id` and never the JWT or payment token. |
| AS-19 | FR-18, 13 | **Asynchronous confirmation.** Given AS-06 returned 202, when the reconciler completes the purchase, then `GET /purchases/{id}` returns `COMPLETED` with the `ticketId`, and exactly one `TicketPurchased` event exists for that purchase. |
| AS-20 | NFR-11 | **Operability.** `/health/ready` of ticketing and `payment-sim` is up in normal operation; with a `PENDING` purchase present, the ticketing metric for pending purchases is 1 and its oldest age grows, then returns to 0 after completion. |
| AS-21 | NFR-13 | **Input validation.** A non-UUID `ticketTypeId`, a negative or non-integer `expectedPriceCents`, or a `paymentMethodToken` outside the allowed format → 400 with the standard error shape; no rows created. |
