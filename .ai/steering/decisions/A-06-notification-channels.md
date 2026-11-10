# ADR A-06: Required Notification Channels

- **Status:** Approved
- **Date:** 2026-11-10
- **Deciders:** Alexandre Faustino (M4 - Notification & Occupancy), Team Consensus
- **Related Requirements:** FR-060, FR-061, FR-062, FR-063, FR-064, FR-065, FR-066, FR-067, FR-068, NFR-021, NFR-042, NFR-056
- **Linear Issue:** [MET-159](https://linear.app/metroisjustabus-ase/issue/MET-159/a-06-confirm-required-notification-channels)

---

## 1. Context and Problem Statement

The course project statement (v1.0, 2026-09-29) mandates that:
1. MetroIsJustABus must notify passengers affected by operational changes (disruptions, delays, cancellations, schedule changes).
2. Passengers must be able to control their subscriptions and notification preferences.
3. The notification capability must be implemented across an independent application boundary (microservice).
4. Temporary failures of the notification component must not affect unrelated system functions (network consultation, ticketing, validation).
5. The system must not send duplicate notifications.

However, the project brief does not fix the specific notification delivery channels. Requirements Specification v0.2 left this under assumption **A-06**:
> *"Working assumption: At least in-app plus one external channel (for example email), with the external channel simulated or sandboxed."*

The team needs an explicit, binding decision on supported channels, their delivery semantics, and how external delivery is sandboxed.

---

## 2. Decision

The team approves assumption A-06 with the following specifications:

### 2.1 Supported Channels
The system supports exactly two channels:
1. **`IN_APP` (In-App Inbox)**:
   - Every passenger has an in-app notification inbox (FR-067).
   - Stored in the Notification Service PostgreSQL database (`notifdb`).
   - Immediately visible to the passenger via authenticated REST API `GET /api/notifications/v1/inbox`.
   - Exactly-once logical representation per `(event_id, user_id, 'IN_APP')` enforced by a database unique constraint (FR-066).

2. **`EMAIL` (Sandboxed Email via Mailpit)**:
   - Sandboxed external delivery using standard SMTP.
   - All outgoing emails are routed to a local **Mailpit** container (`mailpit:1025`) in dev and staging environments.
   - Mailpit provides a web UI (`http://localhost:8025`) and HTTP API to inspect delivered emails and test recipient matching.
   - Real email addresses are never contacted in automated tests or demo environments.

### 2.2 Passenger Preferences (FR-062)
- Passengers configure preferences per channel and change type.
- By default upon registration/first subscription: `IN_APP` is enabled for all change types; `EMAIL` is enabled if a valid email is present.
- A passenger can disable any channel independently.

### 2.3 Delivery and Deduplication Semantics (FR-066, NFR-022)
- **Logical Deduplication Key:** `(event_id, user_id, channel)` enforced in the database.
- Even if RabbitMQ redelivers the same change event multiple times, only one notification record is created per user and channel.
- In-app inbox records are atomic with event consumption.
- Email delivery records store delivery status (`PENDING`, `SENT`, `FAILED`) and attempt count.

---

## 3. Consequences

### Positive
- Fully satisfies the project brief's requirement for independent notification capability and passenger-controlled preferences.
- Mailpit sandbox guarantees zero accidental spam to external domains during testing and evaluation.
- Decouples notification record creation from external SMTP latency, supporting NFR-042 (< 30s target).
- In-app inbox provides deterministic testing in CI/CD without external network access.

### Negative / Trade-offs
- Requires running Mailpit as part of local development compose and CI/CD test stack.
- Exactly-once delivery cannot be physically guaranteed over SMTP network connections; the system guarantees exactly-once notification generation and deduplicated inbox state, with tracked retry attempts for email dispatch.
