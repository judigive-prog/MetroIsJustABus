# ADR A-01: Schedule Variants, Operating Conditions, and Service-Date Precedence

- **Status:** Proposed for Team Approval (pending PR review)
- **Date:** 2026-11-19
- **Author:** João Pedro Xia (`jpx`, Core Backend Lead)
- **Related Requirements:** FR-004, FR-005, FR-006, FR-007, FR-072, FR-073, FR-074, FR-075, FR-105, NFR-033
- **Related Design / Decisions:** DES-01 (`MET-169`), NFR-005 (`MET-87`), A-02 (`MET-155`), E2E-01 (`MET-178`)
- **Linear Issue:** [MET-154](https://linear.app/metroisjustabus-ase/issue/MET-154/a-01-confirm-schedule-variants-and-operating-conditions)

---

## 1. Context and Problem Statement

In Requirements Specification v0.2 (section 5, page 16), assumption **A-01** identifies an unspecified detail in `FR-006` and `FR-072`:

> *"\"Other operational conditions\" for schedule variants is undefined."*
> Working assumption: *"Variants cover day of week and holidays or special dates."*

Before implementing network/schedule persistence (`Schedule`, `ScheduleVariant`, `ScheduledTrip`, `StopTime`, `TripOccurrence`) and date-based timetable lookup (`FR-006`, `FR-072`, `NFR-033`), the team must resolve:
1. Exactly which variant categories and operating conditions are supported in v1.
2. What deterministic precedence rule selects a variant when a calendar date matches multiple rules (e.g., a holiday falling on a Monday, or a special-event date falling on a holiday).
3. How recurring timetable times, `service_date`, overnight trips, and UTC storage (`NFR-033`) interact across Daylight Saving Time (DST) boundaries.

### Alignment with the Original Project Brief (v1.0, 29 September 2026)

Checking pages 7–9 (*Technical Description*, *Schedules, time-dependent validity and exchanged data*, and *Application and Architecture*):
- **Explicitly required by the brief:** Published schedules, trips, passenger consultation of schedules and departures, staff maintenance of schedules/trips, and accurate time-dependent schedule behavior.
- **Not specified by the brief (team-derived choices):** Exact taxonomy of "other operational conditions" (holidays and staff-defined special dates vs. weather/external feeds), variant precedence on overlapping dates, the operating region's local display timezone (`Europe/Lisbon`), and the rule keeping recurring templates in local wall-clock offsets while persisting dated instants in UTC.

---

## 2. Decision

The team adopts the **A-01** working assumption with the following binding rules for MVP (v1):

### 2.1 Supported Schedule Variant Conditions

Schedule variants represent **planned timetable calendars** only. In v1, `ScheduleVariant` and calendar exception rules cover exactly three condition tiers:

| Tier | Priority | Condition Type | Purpose & Scope |
|---|---|---|---|
| 1 | Highest | **`SPECIAL_DATE`** | Staff-defined single-date or bounded-date exception overrides (e.g., special public events, reduced seasonal service, extraordinary operating days configured under `FR-072`). |
| 2 | Medium | **`HOLIDAY`** | Named calendar holidays mapped to explicit dates (`service_date` entries seeded via `DATA-01` or managed by staff). Allows applying a reduced/holiday timetable on a holiday even when it falls on a weekday. |
| 3 | Base | **`WEEKLY`** | Recurring day-of-week patterns covering Monday–Sunday (for example `WEEKDAYS` Mon–Fri, `SATURDAY`, `SUNDAY`, or explicit day-of-week sets). |

Exclusions:
- **No external weather, traffic, or telemetry conditions:** Dynamic external conditions are out of scope (`A-02`).
- **Disruptions are overlays, not schedule variants:** Short-term delays, cancellations, and diversions (`FR-090`–`FR-095`) modify `TripOperationalState` / `Disruption` overlays rather than rewriting `Schedule` or `ScheduleVariant` baseline definitions (`DES-01`, `FR-105`).

### 2.2 Deterministic Date Resolution & Conflict Guard

For any query targeting a calendar date `service_date` on a line:
1. Select the active published `Schedule` revision whose `[valid_from, valid_to]` window covers `service_date`.
2. Evaluate matching variants strictly in descending specificity:
   **`SPECIAL_DATE` > `HOLIDAY` > `WEEKLY`**
3. Exactly **one** variant applies per line and `service_date` (matching the highest-priority rule present).
4. **No fallback invention:** If no variant covers `service_date` within a published schedule (or no schedule covers that date), the system reports **no scheduled service** for that date rather than substituting another day's variant.
5. **Same-tier ambiguity rejected at publish time (`FR-074`):** Publishing a `Schedule` (`draft -> published`) must fail validation if two variants at the **same** priority tier can match the same `service_date` (for instance, two active `WEEKLY` variants both including Monday, or two `SPECIAL_DATE` exceptions targeting the same date).

### 2.3 Timezone, UTC Storage (`NFR-033`), and Overnight / DST Boundaries

1. **Operating region timezone:** The transit region's local timezone defaults to `Europe/Lisbon` (configurable via `OPERATING_TIMEZONE`, resolved via Python's `zoneinfo.ZoneInfo`).
2. **Templates vs. dated instants (`NFR-033`):**
   - Recurring `ScheduledTrip` / `StopTime` template definitions represent local timetable schedule times (or non-decreasing offsets relative to the trip's `service_date` start), so a `08:30` weekday departure remains `08:30` local time before and after DST transitions.
   - Materialized `TripOccurrence` timestamps (`scheduled_departure_at`, `scheduled_arrival_at`), `Disruption` effective periods, and all audit/outbox instants are **persisted strictly in UTC (`tzinfo=UTC`)** and serialized in API responses as ISO-8601 UTC strings ending in `Z` (matching `.ai/steering/conventions.md`). Local conversion to `OPERATING_TIMEZONE` occurs at the query/presentation boundary and when materializing dated `TripOccurrence` instances from templates.
3. **Overnight / post-midnight continuity:** Trips anchored to a `service_date` that extend past local `24:00` retain that `service_date` as their operational service day and use monotonically increasing trip offsets (e.g., `23:50` -> `00:20` represented as `+30 min` relative to trip start), keeping `arrival <= departure` ordering valid across midnight.
4. **DST transition consistency (`MET-107`):** Materializing local `service_date + local_time` via `ZoneInfo` cleanly handles 23-hour spring-forward and 25-hour fall-back transitions without mutating stored UTC instants.

---

## 3. Impact Assessment

- **Requirements & Assumptions:** Confirms the working assumption in `.ai/sdd/specs/domain-data-ownership/assumptions.md` (`A-01`) with explicit specificity rules and timezone policy, leaving all v0.2 priorities unchanged.
- **Unblocked Issues:**
  - **`MET-10` (`FR-006`):** Now has an explicit precedence rule (`SPECIAL_DATE > HOLIDAY > WEEKLY`) and non-overlap publish validation criteria for unit/API tests.
  - **`MET-60` (`FR-072`):** Defines the staff schedule/variant/exception model (`WEEKLY`, `HOLIDAY`, `SPECIAL_DATE`) and same-tier overlap rejection (`FR-074`).
  - **`MET-107` (`NFR-033`):** Confirms UTC storage (`Z`), local `OPERATING_TIMEZONE = "Europe/Lisbon"` conversion, and DST/midnight boundary tests.
- **Data Model (`DES-01` / `MET-169`):** Fits cleanly onto the existing `Schedule` -> `ScheduleVariant` -> `ScheduledTrip` -> `StopTime` -> `TripOccurrence` model without inventing extra services or coupling to external telemetry.
- **Test Scenarios Required:**
  - Ordinary weekday (`WEEKLY`) variant selection.
  - Holiday (`HOLIDAY`) overriding weekday on the same calendar date.
  - Special date (`SPECIAL_DATE`) overriding both `HOLIDAY` and `WEEKLY`.
  - Same-tier overlap rejection during schedule validation/publishing (`FR-074`).
  - Date with no matching variant returning empty departures/service cleanly.
  - Overnight post-midnight trips and `Europe/Lisbon` DST transition round-trips (`NFR-033`).

---

## 4. Consequences

### Positive
- Eliminates ambiguity on how `ScheduleVariant` conditions and overlaps work before building `core-backend` network/schedule models.
- Separates planned calendar variants (`A-01`) cleanly from short-term operational disruptions (`A-02`), preserving published timetable history (`FR-075`, `FR-105`).
- Solves `NFR-033` cleanly by keeping recurring schedules anchored to local wall-clock time in `Europe/Lisbon` while keeping every stored timestamp strictly UTC.

### Negative / Trade-offs
- Assumes a single configured operating timezone (`Europe/Lisbon`) for the network in v1; multi-timezone transit agencies would require a per-line/per-network timezone attribute in a future version.
- Holiday dates must be explicitly provisioned via seed fixtures (`DATA-01`) or staff management endpoints (`FR-072`) rather than fetched dynamically from an external holiday API.
