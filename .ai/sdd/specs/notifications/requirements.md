# Requirements — Notification Service

**Component:** `apps/notification-service`  
**Status:** DRAFT (Milestone 2 enabler)  
**Baseline:** MetroIsJustABus Requirements Specification v0.2 (1 October 2026), Section 2.7, Section 3.3, Section 3.5, Section 5 (A-06).

---

## 1. Functional Requirements

| ID | Requirement | Priority | Source | Linear Issue |
|---|---|---|---|---|
| **FR-060** | A passenger shall be able to subscribe to a line, a stop, or a scheduled trip. | Must | Notifications | [MET-48](https://linear.app/metroisjustabus-ase/issue/MET-48) |
| **FR-061** | A passenger shall be able to list, change and cancel their subscriptions. | Must | Notifications | [MET-49](https://linear.app/metroisjustabus-ase/issue/MET-49) |
| **FR-062** | A passenger shall be able to set notification preferences (at minimum: channel and which types of change they want to receive). | Must | Notifications | [MET-50](https://linear.app/metroisjustabus-ase/issue/MET-50) |
| **FR-063** | When a relevant change occurs (see FR-064), the system shall determine which passengers are affected and notify them. | Must | Notifications | [MET-51](https://linear.app/metroisjustabus-ase/issue/MET-51) |
| **FR-064** | Relevant changes shall include at least: disruption created, updated or ended; trip delayed, cancelled or diverted; schedule changes affecting subscribed entities. | Must | Notifications, Staff | [MET-52](https://linear.app/metroisjustabus-ase/issue/MET-52) |
| **FR-065** | A subscription to a line shall cover its stops and trips. A subscription to a stop shall cover the trips serving it. Overlapping subscriptions shall produce one notification, not several. | Should | Notifications (A) | [MET-53](https://linear.app/metroisjustabus-ase/issue/MET-53) |
| **FR-066** | The same notification shall not be sent more than once to the same passenger, even if the triggering event is redelivered. | Must | Resilience | [MET-54](https://linear.app/metroisjustabus-ase/issue/MET-54) |
| **FR-067** | Passengers shall be able to see a history of notifications they received (in-app inbox). | Should | Lifecycle (A) | [MET-55](https://linear.app/metroisjustabus-ase/issue/MET-55) |
| **FR-068** | Notifications shall respect the passenger's preferences and active subscriptions at the time of the event. | Must | Notifications | [MET-56](https://linear.app/metroisjustabus-ase/issue/MET-56) |
| **FR-069** | Staff changes that affect information in use by passengers shall generate the corresponding notifications. | Must | Staff | [MET-57](https://linear.app/metroisjustabus-ase/issue/MET-57) |
| **FR-102** | A passenger shall access only their own tickets, subscriptions, preferences and notifications. | Must | Accounts (A) | [MET-79](https://linear.app/metroisjustabus-ase/issue/MET-79) |

---

## 2. Non-Functional Requirements & Decisions

| ID | Requirement | Priority | Source | Linear Issue |
|---|---|---|---|---|
| **NFR-002** | Separate the web application, core backend and supporting services. | Must | Architecture | [MET-84](https://linear.app/metroisjustabus-ase/issue/MET-84) |
| **NFR-003** | Each component is built, tested, containerised and deployed independently. | Must | Architecture | [MET-85](https://linear.app/metroisjustabus-ase/issue/MET-85) |
| **NFR-020** | Component failures are isolated: notifications failure must not affect consultation or ticketing. | Must | Resilience | [MET-96](https://linear.app/metroisjustabus-ase/issue/MET-96) |
| **NFR-021** | Notification events shall be retained during notification outages and processed upon recovery. | Must | Resilience (A) | [MET-97](https://linear.app/metroisjustabus-ase/issue/MET-97) |
| **NFR-022** | Communication failures shall not cause duplicate notification delivery. | Must | Resilience | [MET-98](https://linear.app/metroisjustabus-ase/issue/MET-98) |
| **NFR-042** | Notifications should be issued within 30s of event under nominal load. | Should | Performance (A) | [MET-110](https://linear.app/metroisjustabus-ase/issue/MET-110) |
| **NFR-050** | Authenticate users and authorize protected operations by role. | Must | Security | [MET-113](https://linear.app/metroisjustabus-ase/issue/MET-113) |
| **NFR-070** | Correlated structured logging with `X-Correlation-Id`. | Must | Observability | [MET-125](https://linear.app/metroisjustabus-ase/issue/MET-125) |
| **NFR-071** | Health endpoints `/health/live` and `/health/ready`. | Must | Observability | [MET-126](https://linear.app/metroisjustabus-ase/issue/MET-126) |
| **A-06** | Required notification channels: in-app inbox + sandboxed email (Mailpit). | Decision | Assumptions | [MET-159](https://linear.app/metroisjustabus-ase/issue/MET-159) |
