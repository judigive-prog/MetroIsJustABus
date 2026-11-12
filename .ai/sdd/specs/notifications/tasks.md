# Tasks — Notification Service

**Owner:** Alexandre Faustino (M4 - Backend Notifications & Occupancy)  
**Status:** In Progress (BOOT-01 in progress, A-06 approved)

---

## Task Breakdown & Dependency Graph

```text
MET-159 (A-06: Channels) [DONE]
    │
    ▼
MET-171 (BOOT-01: Skeleton & Vertical Slice) [IN PROGRESS]
    │
    ├─────────────────────────────┐
    ▼                             ▼
MET-48 (FR-060: Subscriptions)  MET-50 (FR-062: Preferences)
    │                             │
    ▼                             ▼
MET-49 (FR-061: Manage Subs)    MET-51 (FR-063: Matching)
                                  │
    ┌─────────────────────────────┼─────────────────────────────┐
    ▼                             ▼                             ▼
MET-53 (FR-065: Overlaps)      MET-54 (FR-066: Deduplication)  MET-56 (FR-068: Event Time)
                                  │
                                  ├─────────────────────────────┐
                                  ▼                             ▼
                               MET-55 (FR-067: In-App Inbox)  MET-97 (NFR-021: Outage Recovery)
```

---

## Detailed Task Queue

| Task ID | Title | Linear Issue | Traces | Done When |
|---|---|---|---|---|
| **NOTIF-01** | Confirm notification channels decision A-06 | [MET-159](https://linear.app/metroisjustabus-ase/issue/MET-159) | A-06, FR-062 | ADR committed to `.ai/steering/decisions/` and Linear closed. |
| **NOTIF-02** | Bootstrap notification-service skeleton & plumbing | [MET-171](https://linear.app/metroisjustabus-ase/issue/MET-171) | NFR-002, 003, 070, 071 | Django app, correlation ID middleware, error handler, health endpoints (`/health/live`, `/health/ready`), Dockerfile, and unit tests passing. |
| **NOTIF-03** | Subscriptions API & CRUD | [MET-48](https://linear.app/metroisjustabus-ase/issue/MET-48), [MET-49](https://linear.app/metroisjustabus-ase/issue/MET-49) | FR-060, FR-061, FR-102 | Serializers, views (`POST`, `GET`, `DELETE` on `/api/notifications/v1/subscriptions`), `IsPassenger` permission, DB unique constraints. |
| **NOTIF-04** | Notification Preferences API | [MET-50](https://linear.app/metroisjustabus-ase/issue/MET-50) | FR-062, FR-102, A-06 | `GET`/`PUT` on `/api/notifications/v1/preferences`, channel selection (`IN_APP`, `EMAIL`). |
| **NOTIF-05** | Event Consumer & Affected Passenger Matcher | [MET-51](https://linear.app/metroisjustabus-ase/issue/MET-51), [MET-53](https://linear.app/metroisjustabus-ase/issue/MET-53) | FR-063, FR-064, FR-065 | AMQP consumer for `metro.events`, expansion of line/stop/trip subscriptions, collapse overlapping passenger matches. |
| **NOTIF-06** | Deduplication Engine & Delivery Tracking | [MET-54](https://linear.app/metroisjustabus-ase/issue/MET-54), [MET-56](https://linear.app/metroisjustabus-ase/issue/MET-56) | FR-066, FR-068, NFR-022 | Unique constraint `(event_id, passenger_id, channel)`, event-time preference check, transactional `inbox_event`. |
| **NOTIF-07** | In-App Inbox API | [MET-55](https://linear.app/metroisjustabus-ase/issue/MET-55) | FR-067, FR-102 | `GET /api/notifications/v1/inbox`, mark as read, cursor pagination. |
| **NOTIF-08** | Email Channel via Mailpit & Outage Resilience | [MET-97](https://linear.app/metroisjustabus-ase/issue/MET-97), [MET-110](https://linear.app/metroisjustabus-ase/issue/MET-110) | NFR-021, NFR-042, A-06 | SMTP integration with Mailpit, background retries, fault-injection tests. |
