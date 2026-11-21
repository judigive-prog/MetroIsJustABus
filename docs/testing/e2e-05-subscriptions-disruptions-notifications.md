# E2E-05: Verification of Subscriptions, Staff Disruptions and Targeted Notifications

- **Scenario ID:** E2E-05
- **Linear Issue:** [MET-182](https://linear.app/metroisjustabus-ase/issue/MET-182)
- **Component Scope:** `apps/notification-service`, `apps/core-backend`, RabbitMQ Message Broker
- **Related Requirements & Baseline Keys:** FR-063, FR-064, FR-065, FR-066, FR-067, FR-068, FR-069, ADR A-02, ADR A-06

---

## 1. Purpose and Scope

This end-to-end integration scenario traces staff operational disruption lifecycle events (`DisruptionReported`, `DisruptionUpdated`, `DisruptionResolved`) through the RabbitMQ broker into the `notification-service`. It verifies:
1. **Targeted Recipient Matching (FR-063):** Subscriptions to affected lines, stops, and trips correctly identify impacted passengers.
2. **Hierarchy Expansion & Overlap Deduplication (FR-065):** Line subscriptions automatically cover child stops and trips; passengers with multiple overlapping subscriptions (e.g. subscribed to both Line 1 and a Stop on Line 1) receive exactly **one** notification.
3. **Disruption Lifecycle Progression (FR-064, FR-069):** Progressive updates (Registration -> Extension/Update -> Resolution) accumulate cleanly in the passenger in-app inbox history (FR-067).
4. **Channel Preference Filtering (FR-062, ADR A-06):** In-app and email channels are independently honored; unconfigured or disabled channels are omitted.
5. **Event-Time Preference Validity (FR-068):** Preferences and subscriptions active at the event's `occurred_at` timestamp govern delivery, even if altered after the event occurred.
6. **Delivery Deduplication (FR-066):** Replaying or redelivering a disruption event causes zero duplicate notifications or inbox records.

---

## 2. Recipient Matching Matrix

The following passenger test profiles demonstrate the complete recipient evaluation:

| Passenger Profile | Subscriptions | Preferences | Expected Behavior on Line 1 Disruption |
| :--- | :--- | :--- | :--- |
| **Passenger A** | `LINE: line-1` | `IN_APP: ON`, `EMAIL: ON` | **Matched**: Receives 1 In-App and 1 Email notification per lifecycle event. |
| **Passenger B** | `STOP: stop-101` (on line-1) | `IN_APP: ON`, `EMAIL: OFF` | **Matched**: Receives 1 In-App notification only (Email filtered by preference). |
| **Passenger C** | `TRIP: trip-201` (on line-1) | `IN_APP: ON`, `EMAIL: ON` | **Matched**: Receives 1 In-App and 1 Email notification via hierarchy expansion. |
| **Passenger D (Overlapping)** | `LINE: line-1` AND `STOP: stop-101` | `IN_APP: ON`, `EMAIL: ON` | **Matched & Deduplicated**: Receives **exactly 1** In-App and 1 Email notification (no duplicate for overlapping match). |
| **Passenger E (Unrelated)** | `LINE: line-99` | `IN_APP: ON`, `EMAIL: ON` | **Not Matched**: Receives 0 notifications. |
| **Passenger F (Opted Out)** | `LINE: line-1` | `IN_APP: OFF`, `EMAIL: OFF` | **Filtered**: Receives 0 notifications. |

---

## 3. Disruption Lifecycle Progression

```mermaid
flowchart TD
    Staff[Staff Action in core-backend] -->|1. Register Disruption| Ev1["DisruptionReported (Tree on tracks)"]
    Staff -->|2. Update Disruption| Ev2["DisruptionUpdated (Delay extended to 45m)"]
    Staff -->|3. Close Disruption| Ev3["DisruptionResolved (Tracks cleared, normal service)"]

    Ev1 -->|RabbitMQ| Consumer[Notification Event Consumer]
    Ev2 -->|RabbitMQ| Consumer
    Ev3 -->|RabbitMQ| Consumer

    Consumer -->|Record inbox_event| DB[(notifdb)]
    Consumer -->|Append to In-App Inbox (FR-067)| Inbox[Passenger Inbox History]
    Consumer -->|Dispatch to Mailpit (ADR A-06)| Email[Sandboxed Email Dispatch]
```

### Verified Inbox History:
- For affected passengers, notifications are listed in reverse chronological order (newest first per `conventions.md`):
  1. `Line 1 Service Restored` (`DisruptionResolved`)
  2. `Line 1 Delay Extended to 45m` (`DisruptionUpdated`)
  3. `Line 1 Track Obstruction` (`DisruptionReported`)
- Passenger read management (`mark_as_read`, `mark_all_as_read`) operates without errors and updates unread counts deterministically.

---

## 4. Test Evidence & Traceability

- **Automated Test File:** [`apps/notification-service/notifications/tests/test_e2e_subscriptions_disruptions.py`](file:///Users/alex/Documents/mei/ASE/Project/MetroIsJustABus/apps/notification-service/notifications/tests/test_e2e_subscriptions_disruptions.py)
- **Requirement Markers:** `@pytest.mark.req("E2E-05", "FR-063", "FR-065", "FR-066", "FR-067", "FR-068", "FR-069")`
- **Pass Rate:** 100% passed across all scenarios.
