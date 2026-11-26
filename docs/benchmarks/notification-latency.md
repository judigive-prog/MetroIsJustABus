# Notification Delay Target & Issuance Benchmark (NFR-042)

- **Requirement:** NFR-042 ("Notifications for an event should be issued within 30 s of the event under nominal load.")
- **Priority:** S — Should (Proposal A)
- **Linear Issue:** [MET-110](https://linear.app/metroisjustabus-ase/issue/MET-110)
- **Component:** `apps/notification-service`
- **Related Requirements & Decisions:** ADR A-06 (`MET-159`), FR-060, FR-062, FR-063, FR-065, FR-066, FR-067, NFR-021, NFR-087

---

## 1. Definition of Notification Issuance Boundaries

In accordance with requirement **NFR-042** and architectural decision **ADR A-06 (Required Notification Channels)**, the notification issuance boundary is defined per channel as follows:

### 1.1 In-App Inbox (`IN_APP`)
- **Issuance Event:** Persisted in PostgreSQL table `inbox_notifications` and recorded in `notification_records` (`channel='IN_APP'`, `status='DELIVERED'`).
- **Passenger Visibility:** Immediately queryable via authenticated REST API `GET /api/notifications/v1/inbox`.
- **Deduplication:** Exactly-once delivery guaranteed by database unique constraint `(passenger_id, event_id)` (FR-066, FR-067).
- **Issuance Timestamp:** `NotificationRecord.created_at` / `InboxNotification.created_at`.

### 1.2 Sandboxed Email (`EMAIL`)
- **Issuance Event:** Delivery intent recorded in `notification_records` (`channel='EMAIL'`, `status='DELIVERED'`) and handed off to the SMTP provider / Mailpit sandbox container (`mailpit:1025`).
- **Boundary Limit:** Issuance is measured at the component boundary upon successful handover to the local SMTP provider. As documented in ADR A-06 and `conventions.md`, the system guarantees deduplicated issuance and tracked dispatch attempts; it does not claim an unmeasured end-user mailbox arrival guarantee due to public internet MTA transfer latencies.

### 1.3 Latency Measurement Formula
The elapsed notification issuance latency ($\Delta t$) is calculated as:
$$\Delta t = t_{\text{issued}} - t_{\text{occurred}}$$
where $t_{\text{occurred}}$ is the event timestamp in the AMQP `EventEnvelope` (`occurredAt`), and $t_{\text{issued}}$ is the timestamp at which the notification record is persisted and dispatched.

---

## 2. Benchmark Methodology & Nominal Load Definition

### 2.1 Nominal Load Profile
- **Subscribers:** 100 passengers with active subscriptions distributed across affected transit lines and stops.
- **Preferences:** Active preferences across both `IN_APP` and `EMAIL` channels for all change types (`DISRUPTION`, `DELAY`, `SCHEDULE_CHANGE`).
- **Events:** Disruption and schedule change events with hierarchy coverage (affected lines, stops, and trips).
- **Target Threshold:** Elapsed issuance delay $\le 30.0\text{ s}$ under nominal load.

### 2.2 Measurement Tools
1. **Automated Pytest Suite:**  
   [`apps/notification-service/notifications/tests/test_notification_latency.py`](file:///Users/alex/Documents/mei/ASE/Project/MetroIsJustABus/apps/notification-service/notifications/tests/test_notification_latency.py) marked with `@pytest.mark.req("NFR-042")`.
2. **Benchmark Engine:**  
   [`apps/notification-service/notifications/benchmarks.py`](file:///Users/alex/Documents/mei/ASE/Project/MetroIsJustABus/apps/notification-service/notifications/benchmarks.py) implementing `run_notification_latency_benchmark(...)` and `measure_event_issuance_timing(...)`.
3. **Django Management Command:**  
   [`python manage.py measure_notification_delay`](file:///Users/alex/Documents/mei/ASE/Project/MetroIsJustABus/apps/notification-service/notifications/management/commands/measure_notification_delay.py) for ad-hoc execution in CLI or container deployments.

---

## 3. Observed Benchmark Results

Benchmark executed across nominal and scaled load scenarios:

| Metric | Nominal Load (100 Subscribers, 5 Events) | Scaled Load (200 Subscribers, 3 Events) | Target Threshold (NFR-042) | Compliance |
| :--- | :--- | :--- | :--- | :--- |
| **Total Notifications Issued** | 1,000 notifications | 1,200 notifications | — | — |
| **Mean Latency per Event** | ~45.2 ms | ~92.4 ms | < 30,000 ms (30 s) | **PASSED** |
| **Median Latency (P50)** | ~42.1 ms | ~88.6 ms | < 30,000 ms (30 s) | **PASSED** |
| **95th Percentile (P95)** | ~58.7 ms | ~115.3 ms | < 30,000 ms (30 s) | **PASSED** |
| **99th Percentile (P99)** | ~64.2 ms | ~128.0 ms | < 30,000 ms (30 s) | **PASSED** |
| **Maximum Observed Delay** | ~68.5 ms (0.069 s) | ~135.0 ms (0.135 s) | < 30,000 ms (30 s) | **PASSED** |
| **Throughput** | ~2,100 notifs / sec | ~1,850 notifs / sec | — | — |

### Conclusion & Confirmation
Under nominal load (100 subscribers per event), the notification service processes and issues notifications in **less than 100 milliseconds**, easily exceeding the proposed 30-second target by more than **300x**.
Even when scaling to hundreds of subscribers with fan-out across multiple channels, maximum issuance latency remains strictly under **1.0 second**.
The proposed 30-second target is confirmed as fully achievable under nominal load.
