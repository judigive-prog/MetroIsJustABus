# Ticket Validation — Requirements

**Status:** draft for team review (PL6, 2026-10-27). Generated with an AI assistant from the sources below; every decision marked *proposed* needs team confirmation.
**Component:** `apps/ticketing-service`
**Sources:** project statement v1.0 (2026-09-29), requirements specification v0.2 (FR-040 to FR-048, NFR-013, NFR-022, NFR-030, NFR-041, NFR-053, A-05, A-08, A-13), steering files in `.ai/steering/`.

## 1. Feature description

> As a **validator** at a stop entrance, I submit a ticket that a passenger presents, so that the system tells me immediately whether the passenger may board, records the use, and updates the ticket — exactly once, even if my request is retried or the same ticket is presented at two validators at the same time.

### In scope
- Validation decision for one presented ticket (accept or reject with a reason)
- Recording every attempt, accepted or rejected
- Updating the ticket after an accepted validation (remaining journeys, start of validity period, lifecycle state)
- Idempotent handling of retried requests and safe handling of concurrent validations of the same ticket
- Publishing a `TicketValidated` event for accepted validations (written to the outbox)

### Out of scope (other features)
- Buying tickets and managing ticket types (FR-030 to FR-037, FR-080, FR-081)
- Passenger view of their validation history (FR-034) and staff queries on validation activity (FR-082 to FR-084)
- Consuming `TicketValidated` in the occupancy service (FR-050, FR-051) and the outbox relay process
- Registering and managing validators (no staff function exists for this yet; see OQ-04)

## 2. Supporting passages in the project statement

| Ref | Quotation (Technical Description) | Used for |
|---|---|---|
| S-1 | "Tickets must be validated when they are used." | The feature itself |
| S-2 | "MetroIsJustABus must determine whether a ticket is valid for the attempted use and record successful validations." | Decision, recording |
| S-3 | "Ticket validity may depend on the type of ticket, its current state, previous validations, and the time at which it is used." | Validity rules |
| S-4 | "Ticket types may differ in their price, period of validity, conditions of use, or number of permitted journeys." | Rule model |
| S-5 | "…handle communication failures without causing unintended effects, such as … recording the same validation … multiple times." | Idempotency |
| S-6 | "Passenger activity, including ticket validations, may affect the occupancy information associated with a trip." | Event to occupancy |
| S-7 | "Operational staff should be able to obtain information about ticket usage and validation activity." | Recording rejected attempts |
| S-8 | Application and Architecture: interfaces between components must be explicit; communication failures, retries and duplicates must be handled. | API, event, failure cases |

The statement does **not** say where validation happens, what a validator sends, when a validity period starts, or what counts as one "journey".

## 3. Actors, inputs, outputs, dependencies

| | |
|---|---|
| Primary actor | Validator: fixed device at a stop or station entrance (A-05, A-13). A system actor, not a person. In tests and the demo, `validator-sim` |
| Secondary actor | Passenger, who presents the ticket. Does not call the API |
| Input | Ticket id read from the presented ticket, device time, idempotency key, validator credential |
| Output | Result (`ACCEPTED` or `REJECTED`), rejection reason, ticket summary after the decision |
| Stored effects | Validation attempt record; ticket update and state-change record (accepted only); outbox event (accepted only) |
| Depends on | Ticketing database (tickets with their terms snapshot, validator registry); validator authentication (OQ-03) |
| Downstream | Occupancy service consumes `TicketValidated` asynchronously. Validation never waits for it (NFR-020) |

## 4. Assumptions and decisions

Items marked **Stated** come from the statement or an approved v0.2 assumption. Items marked **Proposed** are team decisions made for this feature and need confirmation.

| ID | Decision | Basis | Status |
|---|---|---|---|
| D-01 | Validation happens at the stop entrance before boarding. The request carries no line or trip. Tickets are valid on all lines | A-05, A-13, A-08 | Stated (v0.2) |
| D-02 | The server's clock at the moment the request is first processed is the authoritative time of use. The device time is stored for audit only and never used in the decision | Conventions require a defined decision time and forbid trusting device time. A device clock can be wrong or tampered with | Proposed |
| D-03 | The stop is derived from the authenticated validator's registration, never taken from the request body | Conventions: "how an authenticated validator is bound to a stop" | Proposed |
| D-04 | A period-based ticket's validity period starts at its first accepted validation, not at purchase | FR-044 gives "start the validity period" as an example of a validation effect. S-4 does not say when a period starts | Proposed |
| D-05 | Each accepted validation of a journey-based ticket consumes exactly one journey. There is no transfer window | S-4 says "number of permitted journeys" but does not define a journey. Simplest rule that can be tested; see OQ-01 | Proposed |
| D-06 | An unknown ticket id is a business rejection (`200`, `REJECTED`, `UNKNOWN_TICKET`), not a `404` | FR-042 lists "unknown ticket" as a rejection reason; the validator needs one uniform outcome to show the passenger. Conflicts with the general conventions rule; see review finding F-01 | Proposed |
| D-07 | Rejected attempts are recorded as well as accepted ones | FR-047 (Should), supported by S-7 "validation activity" | Stated (v0.2, assumption) |
| D-08 | The `TicketValidated` event carries no ticket or passenger identifier | Occupancy only needs stop and time (A-03). Data minimisation (NFR-056) | Proposed |
| D-09 | Validators are online. Offline buffering and late batch submission are not supported | Not in the statement. Supporting them would change the decision-time rule (D-02) | Proposed |
| D-10 | Validity rules come from the ticket's immutable terms snapshot (journeys, period, absolute expiry), so new ticket types need no code change | FR-048, FR-081 | Stated (v0.2) |
| D-11 | When several rejection reasons apply, one is returned in a fixed order: unknown, cancelled, expired, no journeys left | FR-042 asks for "a reason", not all of them. A fixed order makes the result testable. The order itself is a team choice (most permanent cause first) | Proposed |

## 5. Functional requirements

| ID | Requirement | Source | Pri |
|---|---|---|---|
| TV-REQ-01 | The system shall accept a validation request containing a ticket id and the device time, sent by an authenticated validator with an idempotency key. The stop is derived from the validator (D-03) | FR-040, D-01, D-03 | Must |
| TV-REQ-02 | The system shall decide whether the ticket is valid at the authoritative time of use (D-02), considering the ticket's terms snapshot, current state and previous accepted validations | FR-041, S-3, D-10 | Must |
| TV-REQ-03 | The system shall reject an invalid attempt with exactly one reason from: `UNKNOWN_TICKET`, `CANCELLED`, `EXPIRED`, `NO_JOURNEYS_LEFT`. When several apply, the first in that order is returned (D-11) | FR-042, D-11 | Must |
| TV-REQ-04 | The system shall record every accepted validation with ticket, validator, stop and time of use | FR-043, S-2 | Must |
| TV-REQ-05 | An accepted validation shall update the ticket: decrement remaining journeys where the ticket has a journey limit (D-05); start the validity period on first use where the ticket has a period (D-04); move the ticket from `ISSUED` to `ACTIVE`, or to `USED_UP` when no journeys remain. Each state change is appended to the ticket's state history | FR-044, FR-035 | Must |
| TV-REQ-06 | A request repeated with the same idempotency key and the same ticket id by the same validator shall return the original result and shall not create a second record or a second state change, even if the device time differs. The same key with a different ticket id shall be refused with `409 IDEMPOTENCY_KEY_REUSED` | FR-045, NFR-013, S-5 | Must |
| TV-REQ-07 | Concurrent validations of the same ticket shall be serialised so that the ticket is never used beyond its journey limit or validity period | FR-046, NFR-030 | Must |
| TV-REQ-08 | Every rejected attempt shall be recorded with its reason, validator, stop and time | FR-047, D-07 | Should |
| TV-REQ-09 | An accepted validation shall emit exactly one `TicketValidated` event, written in the same transaction as the validation. Rejected attempts emit no event | NFR-015, S-6, principle 1 | Must |
| TV-REQ-10 | Only an authenticated, active validator may submit validations. Passenger and staff credentials shall be refused | NFR-050, NFR-053, conventions | Must |
| TV-REQ-11 | A ticket whose terms define an absolute expiry, or whose validity period has ended, shall be marked `EXPIRED` when a validation detects it, with a state-change record | FR-035, S-3 | Should |

## 6. Non-functional constraints for this feature

| ID | Constraint | Source |
|---|---|---|
| TV-NFR-01 | Result returned in under 1 s at the 95th percentile under nominal load (proposed target, confirmed by a later performance test) | NFR-041 |
| TV-NFR-02 | Validation does not depend on the occupancy or notification service or on the broker being available | NFR-020, principle 5 |
| TV-NFR-03 | No personal data in logs. The ticket id is logged only as part of the attempt record, never with passenger identity | NFR-056 |
| TV-NFR-04 | All decisions read time from the injected clock, so tests control it | NFR-033, conventions |

## 7. Acceptance scenarios

Common setup: validator `V1` is active and registered at stop `S1`; the clock is fixed per scenario. "10-journey ticket" means terms `{journeys: 10, period: none, expiresAt: none}`. "24 h pass" means terms `{journeys: none, period: 24 h, expiresAt: none}`.

| ID | Given | When | Then | Covers |
|---|---|---|---|---|
| TV-AC-01 | A 10-journey ticket in `ISSUED` with 10 journeys left | `V1` validates it | `200 ACCEPTED`; 9 journeys left; state `ACTIVE`; one validation record with stop `S1`; one `TicketValidated` event in the outbox | 01, 02, 04, 05, 09 |
| TV-AC-02 | A journey ticket in `ACTIVE` with 1 journey left | `V1` validates it | `ACCEPTED`; 0 left; state `USED_UP` | 05 |
| TV-AC-03 | A journey ticket in `USED_UP` | `V1` validates it | `REJECTED`, reason `NO_JOURNEYS_LEFT`; a rejected-attempt record; no event; ticket unchanged | 03, 08, 09 |
| TV-AC-04 | A 24 h pass in `ISSUED`, clock at 2026-11-20T08:00Z | `V1` validates it | `ACCEPTED`; period starts at 08:00Z and ends 2026-11-21T08:00Z; state `ACTIVE` | 05 (D-04) |
| TV-AC-05 | That pass, activated at 2026-11-20T08:00Z, clock at 2026-11-20T18:00Z | `V1` validates it | `ACCEPTED`; period end unchanged | 02 |
| TV-AC-06 | That pass, clock at 2026-11-21T08:00Z | `V1` validates it | `REJECTED`, reason `EXPIRED`; state `EXPIRED` with a state-change record | 03, 11 |
| TV-AC-07 | A ticket in `CANCELLED` | `V1` validates it | `REJECTED`, reason `CANCELLED` | 03 |
| TV-AC-08 | No ticket with the presented id | `V1` validates it | `200 REJECTED`, reason `UNKNOWN_TICKET`; a rejected-attempt record | 03, 08 (D-06) |
| TV-AC-09 | TV-AC-01 has completed with key `K1` | `V1` repeats the same request with `K1` | Same response body as the first; still 9 journeys left; still one validation record and one event | 06 |
| TV-AC-10 | TV-AC-01 has completed with key `K1` | `V1` sends key `K1` with a different ticket id | `409 IDEMPOTENCY_KEY_REUSED`; nothing recorded | 06 |
| TV-AC-10b | TV-AC-01 has completed with key `K1` | `V1` repeats it with key `K1`, the same ticket id and a device time 5 s later | Same response as the first; no second effect | 06 |
| TV-AC-11 | A journey ticket with 1 journey left | `V1` and `V2` validate it at the same moment with different keys | Exactly one `ACCEPTED` and one `REJECTED` (`NO_JOURNEYS_LEFT`); 0 left; one event | 07 |
| TV-AC-12 | The broker and the occupancy service are stopped | `V1` validates a valid ticket | `ACCEPTED` within the normal time; the event stays pending in the outbox | 09, TV-NFR-02 |
| TV-AC-13 | A valid ticket; the device time in the request is 2 hours behind the server clock | `V1` validates it | The decision and the recorded time of use use the server clock; the device time is stored separately | 02 (D-02) |
| TV-AC-14 | A request with no credential, with a passenger token, or from a deactivated validator | It is sent | `401`, `403`, `403` respectively; nothing recorded | 10 |
| TV-AC-15 | The ticketing database is unavailable | `V1` validates a ticket | `503 DEPENDENCY_UNAVAILABLE`; a later retry with the same key is processed normally | 06, conventions |

## 8. Open questions

| ID | Question | Impact | Blocks PL7? |
|---|---|---|---|
| OQ-01 | Does a transfer (a second validation shortly after the first, at another stop) consume another journey? | D-05 assumes yes. A transfer window would change TV-REQ-05 and add scenarios | No: implement D-05; revisit |
| OQ-02 | A passenger taps the same journey ticket twice by mistake at the same validator (two different requests). Should the second be refused or ignored for a short time (anti-passback)? | Without a rule, the second tap consumes a journey (consistent with D-05) | No, but it should be raised with the lecturers |
| OQ-03 | How are validator credentials issued and revoked? The tech stack says "service credentials" but names no issuer | TV-REQ-10 needs a working credential | Partly: PL7 can use a test token signed with the dev key; production issuing stays open |
| OQ-04 | Who registers validators and binds them to stops (staff UI, seed data, admin command)? | D-03 needs the registry to be filled | No: seed data for PL7 |
| OQ-05 | Can a ticket be bought for a future start date (not valid yet)? | Would add a `NOT_YET_VALID` reason | No: not supported now |
| OQ-06 | Is the 1 s target (NFR-041) confirmed? | Performance test threshold | No |
