# ADR A-02: Source of Delays, Disruptions, and Simulator Boundary

- **Status:** Proposed for Team Approval (pending PR review)
- **Date:** 2026-11-19
- **Author:** João Pedro Xia (`jpx`, Core Backend Lead)
- **Related Requirements:** FR-010–FR-014, FR-063, FR-064, FR-090–FR-096, FR-101, FR-105, NFR-042, NFR-050, NFR-053, NFR-057
- **Related Design / Decisions:** DES-01 (`MET-169`), NFR-005 (`MET-87`), A-01 (`MET-154`), A-07 (`MET-160`), E2E-01 (`MET-178`), E2E-05 (`MET-182`)
- **Linear Issue:** [MET-155](https://linear.app/metroisjustabus-ase/issue/MET-155/a-02-confirm-the-source-of-delays-and-disruptions)

---

## 1. Context and Problem Statement

In Requirements Specification v0.2 (section 5, page 16), assumption **A-02** flags an unspecified source of live delay and disruption data:

> *"Where delay information comes from is not stated (no vehicle tracking is mentioned)."*
> Working assumption: *"Delays, cancellations and diversions are registered by staff as disruptions; there is no live GPS feed. For tests and the demo, a disruption simulator generates them through the staff interface (FR-096). Passengers are notified as soon as a disruption is registered (FR-063, NFR-042)."*

Before implementing disruption management (`FR-090`–`FR-096`), operational trip projections (`FR-010`–`FR-014`), and notification propagation (`FR-063`, `FR-064`), the team must confirm:
1. Whether any real-time vehicle tracking / GPS telemetry integration exists in v1.
2. How the disruption simulator interacts with `core-backend` (`FR-096`) without introducing backdoors or bypassing staff authorization/auditing.
3. How simulated inputs are identified in audit logs and isolated from production environments.

### Alignment with the Original Project Brief (v1.0, 29 September 2026)

Checking pages 7–9 (*Technical Description* and *Application and Architecture*):
- **Explicitly required by the brief:** Operational staff registration and management of disruptions (delays, cancellations, diversions, affected entities and operating periods), propagation to passenger consultation and notifications, and history/audit recording.
- **Not specified by the brief (team-derived choices):** Absence of live vehicle GPS/AVL telemetry, use of a disruption simulator for testing and demos (`FR-096`), routing the simulator strictly through the supported staff HTTP boundary, and tagging simulated disruption actions explicitly in audit records.

---

## 2. Decision

The team confirms and adopts the **A-02** working assumption with the following binding rules for MVP (v1):

### 2.1 Authoritative Disruption Source (No Live GPS/Telemetry Feed)

1. **Staff-registered disruptions only:** Delays, cancellations, diversions, and other service disruptions originate solely from `Disruption` records managed inside `core-backend` (`FR-090`–`FR-095`). No live vehicle GPS, AVL, or external telemetry pipeline is built or required in v1.
2. **Baseline timetable preservation (`FR-105`, `DES-01`):** Disruption records project operational overrides (`TripOperationalState` / disruption overlay) over published timetables without destroying published `Schedule`, `ScheduledTrip`, or `StopTime` baselines.
3. **Atomic propagation (`FR-063`, `FR-064`, `FR-093`, `NFR-042`):** Creating, updating, extending, or closing a disruption commits the `Disruption`, `DisruptionScope`, `DisruptionChange` / `StaffAudit` record, and local outbox intent (`DisruptionChanged` / `TripStatusChanged`) in a single `core-backend` database transaction so passenger views and `notification-service` receive changes promptly.

### 2.2 Disruption Simulator Boundary (`FR-096`)

For automated scenarios and demonstrations without live operational staff clicking the UI:
1. **Same staff API boundary — no backdoors:** The disruption simulator must call the exact same `/api/core/v1/staff/disruptions` endpoints used by the operational staff UI (`create`, `update`/`extend`, `close`). It must never write directly to `core-backend`'s database, publish raw messages straight to RabbitMQ, or bypass `JWTAuthentication` and `IsStaff` (`NFR-050`, `NFR-053`).
2. **Provisioned test/demo staff credentials:** The simulator authenticates using dedicated non-production test staff credentials configured in the test/dev environment (`NFR-095`).
3. **Explicit source labelling in audit and records:** `Disruption` and `DisruptionChange` / `StaffAudit` record an explicit `source` classification (`STAFF` vs. `SIMULATOR`) alongside `author_id`, allowing simulated inputs to be inspected and distinguished from manual operator edits in historical views (`FR-095`, `FR-096`) while still triggering authentic cross-component behavior (passenger API overlays + RabbitMQ notifications).
4. **Environment isolation (`NFR-095`):** The disruption simulator is strictly a development, testing, and demonstration tool. It is never deployed or granted active credentials in a production environment.

---

## 3. Impact Assessment

- **Requirements & Assumptions:** Preserves the working assumption in `.ai/sdd/specs/domain-data-ownership/assumptions.md` (`A-02`) and `FR-096` without altering v0.2 priorities.
- **Unblocked Issues:**
  - **`MET-76` (`FR-096`):** Confirms the simulator authenticates against `/api/core/v1/staff/disruptions`, preserves `IsStaff` authorization, labels generated actions as `SIMULATOR`, and demonstrates end-to-end passenger information and notification propagation.
- **Components Affected:**
  - `apps/core-backend` (`FR-090`–`FR-095`): implements staff disruption endpoints, `Disruption` + `DisruptionChange` + `StaffAudit` persistence with `source` (`STAFF` / `SIMULATOR`), operational schedule overlay queries (`FR-010`–`FR-014`), and transactional outbox event emission.
  - `simulators/disruption-sim` (planned under `MET-76`): implements an HTTP client driving `/api/core/v1/staff/disruptions` using test staff credentials; zero direct DB/broker access.
  - `apps/notification-service` & `apps/web`: consume the exact same disruption events and query endpoints whether created manually by staff or driven by the simulator.
- **Verification Criteria (`FR-096`, `E2E-01`, `E2E-05`):**
  1. Simulator creates, updates, and closes a disruption solely via the staff HTTP API (`401`/`403` enforced if unauthenticated or non-staff).
  2. Resulting disruption and change history record `source = SIMULATOR` and `author_id`.
  3. Passenger schedule/departure APIs reflect the disruption overlay and `notification-service` emits real notifications for affected subscribers without any GPS feed.

---

## 4. Consequences

### Positive
- Eliminates external vehicle-telemetry dependencies while keeping end-to-end operational disruption, passenger consultation, and notification workflows completely realistic and testable.
- Exercises the genuine production staff API, validation, authorization (`IsStaff`), audit trail, and outbox pipeline during every demo and test run.
- Clearly separates simulated demo traffic from human operator actions via explicit `source` metadata and dev/test credential boundaries.

### Negative / Trade-offs
- Operational delays only appear in the system when registered by staff (or generated by the simulator in dev/demo) — real-time automatic delay inference from vehicle movement is out of scope for v1.
- Running the simulator in a shared dev environment triggers real dev-stack notifications to test accounts subscribed to affected entities unless targeted/cleaned between demo scenarios.
