# ADR A-03: Boarding Attribution, Capacity, and Occupancy Estimation

- **Status:** Proposed for Team Approval (pending PR review)
- **Date:** 2026-11-19
- **Author:** João Pedro Xia (`jpx`, Core Backend Lead)
- **Related Requirements:** FR-009, FR-040–FR-043, FR-047, FR-050–FR-056, FR-103, NFR-015, NFR-020, NFR-024, NFR-056
- **Related Design / Decisions:** DES-01 (`MET-169`), NFR-005 (`MET-87`), A-05 (`MET-158`), A-11 (`MET-164`), A-13 (`MET-166`), E2E-04 (`MET-181`)
- **Linear Issue:** [MET-156](https://linear.app/metroisjustabus-ase/issue/MET-156/a-03-confirm-boarding-attribution-and-occupancy-estimation)

---

## 1. Context and Problem Statement

In Requirements Specification v0.2 (section 5, page 16), assumption **A-03** identifies an open measurement/modelling ambiguity:

> *"How 'occupancy' is measured is not stated. In practice validators only record boardings (tap-in) at a stop, outside the vehicle, with no line or trip."*
> Working assumption: *"Occupancy is estimated, not measured. Boardings at a stop are attributed to the trips serving that stop up to the next departure, split by each line's share of historical demand (equal shares initially). Alighting is not tracked, so the real onboard load and over-capacity cannot be known; estimates are most useful aggregated over time (peak hours, busiest trips)."*

Before implementing capacity management (`FR-050`, `FR-054`), boarding attribution (`FR-051`), and occupancy/crowding queries (`FR-009`, `FR-052`, `FR-053`, `FR-056`), the team must establish:
1. Exactly how entrance validations are matched to candidate scheduled trips (`TripOccurrence`) at a shared stop and across departure boundaries.
2. How historical-demand weights and the initial equal-share fallback are computed and recorded.
3. How total capacity, derived estimated occupancy/remaining capacity, missing history, and stale/unavailable states are represented without misrepresenting estimates as measured onboard load.

### Alignment with the Original Project Brief (v1.0, 29 September 2026)

Checking pages 7–9 (*Technical Description* and *Application and Architecture*):
- **Explicitly required by the brief:** Monitoring scheduled-trip occupancy and available capacity (`FR-050`–`FR-056`), providing capacity/occupancy views for operational staff and (where appropriate) passengers, and preventing duplicate validation/activity counting.
- **Not specified by the brief (team-derived choices):** Entrance-only validation without line/trip context (`A-13`), absence of passenger alighting/tap-out data, boarding-attribution candidate windows, historical-demand share weighting with equal-share fallback, and explicit `estimated` semantics rather than exact onboard headcounts.

---

## 2. Decision

The team confirms and adopts the **A-03** working assumption with the following binding attribution and estimation rules for MVP (v1):

### 2.1 Accepted Validation Input & Idempotency

1. **Anonymized boarding observation (`NFR-015`, `NFR-056`):** Only **accepted** entrance validations (`TicketValidated` events carrying `event_id`, `stop_id`, and server-authoritative `validated_at` UTC timestamp — with **no** ticket/passenger identifier and **no** inferred line/trip) count as boarding observations. Rejected validation attempts emit no event.
2. **Deduplication & out-of-order resilience:** `occupancy-service` deduplicates incoming `event_id` values in the same local database transaction (`BoardingObservation`) as its derived attribution updates (`DES-01`). Broker redeliveries or out-of-order events never double-count boardings and never discard distinct events.

### 2.2 Candidate Trip Window & Next-Departure Boundary (`FR-051`)

For a boarding observation `(stop_id, validated_at)`:
1. **Eligible trips:** Consider non-cancelled `TripOccurrence` instances (projected from `core-backend`, incorporating effective operational times under `A-01`/`A-02`) serving `stop_id`.
2. **Next-departure-per-line/direction rule:** Within a configurable pre-boarding lookahead horizon (`ATTRIBUTION_WINDOW_MINUTES = 60` minutes by default), select at most **one upcoming departure per active line/route-pattern** serving `stop_id` — specifically the earliest eligible `effective_departure_at >= validated_at`.
3. **Exact boundary semantics:**
   - A tap-in at `validated_at == effective_departure_at` remains eligible for that departing trip (`>=` inclusive).
   - A tap-in strictly after departure (`validated_at > effective_departure_at`) rolls forward to the next eligible departure within the lookahead window.
   - If no non-cancelled trip departs within the horizon (`k = 0`), persist `BoardingObservation` explicitly as unattributed (`attributed = false`) for traceability rather than failing or fabricating a match.

### 2.3 Weighting, Equal-Share Fallback & Conservation (`FR-051`)

Given the candidate set $T = \{t_1, \dots, t_k\}$ ($k \ge 1$):
1. **Conservation invariant:** Assigned fractional shares $w_i$ must sum to `1.0` ($\sum_{i=1}^{k} w_i = 1.0$) so every attributed validation contributes exactly `1.0` total boarding across $T$. Single-candidate stops ($k = 1$) receive $w_1 = 1.0$.
2. **Historical-demand weighting:** When configured or historical validated-demand weights $(d_1, \dots, d_k)$ with $\sum d_j > 0$ are available for the lines/patterns serving `stop_id` in the relevant time window, allocate proportional weights $w_i = d_i / \sum_{j=1}^{k} d_j$ and record `rule_version` + `allocation_mode = "HISTORICAL_DEMAND"`.
3. **Initial equal-share fallback:** Whenever historical-demand weights are absent or total zero (including initial cold start), distribute weights uniformly ($w_i = 1 / k$) and record `allocation_mode = "EQUAL_SHARE"`.

### 2.4 Capacity, Derived Available Capacity & Estimation Honesty (`FR-050`, `NFR-024`)

1. **Stored capacity vs. derived estimates (`MET-41`):**
   - `TripCapacity` (owned by `occupancy-service`, positive integer `capacity > 0`, configurable via `FR-054`) stores total vehicle/trip capacity separately from derived values.
   - `OccupancyEstimate` records `estimated_boardings` (floating/rounded aggregate of `BoardingAttribution` shares) and derives `estimated_available_capacity = max(0, capacity - round(estimated_boardings))` explicitly as an estimate — never altering stored `capacity` and never overwriting historical `TripCapacity` snapshots (`FR-054`, `FR-103`).
2. **No measured onboard load or proven over-capacity:** Because alighting is untracked, `OccupancyEstimate` responses must label estimates explicitly (`is_estimated: true`, `alighting_tracked: false`, `as_of`, `rule_version`) and never represent boarding-derived totals as exact measured onboard headcounts or legal over-capacity violations.
3. **Stale / missing data visibility (`NFR-024`):** If schedule projections are stale or no `TripCapacity` configuration exists for a trip, report explicit `completeness` / `status` metadata (such as `UNKNOWN` or `STALE`) rather than fabricating `0` occupancy.
4. **Public exposure boundary (`A-11`):** Staff indicators (`FR-052`) may view numeric estimates and capacity utilization summaries; public passenger trip displays (`FR-009`, `FR-053`) remain subject to **`A-11` (`MET-164`)** (coarse crowding indicator levels vs. raw numbers).

---

## 3. Impact Assessment

- **Requirements & Assumptions:** Preserves the working assumption in `.ai/sdd/specs/domain-data-ownership/assumptions.md` (`A-03`), clarifying exact boundary rules, conservation, and `capacity` vs `estimatedAvailableCapacity` separation for `FR-050`–`FR-056`.
- **Unblocked Issues:**
  - **`MET-41` (`FR-050`):** Confirms `TripCapacity` vs `OccupancyEstimate` separation, derived available capacity, and explicit missing/stale presentation.
  - **`MET-42` (`FR-051`):** Fixes exact candidate-window rules (`>= validated_at`, bounded lookahead), next-departure boundary, historical-demand weights, and equal-share fallback.
- **Components Affected:**
  - `apps/ticketing-service`: emits anonymized `TicketValidated` (`event_id`, `stop_id`, `validated_at` only; no passenger/ticket IDs, no line/trip guess).
  - `apps/core-backend`: publishes/projects non-cancelled dated stop departure projections consumed by `occupancy-service`.
  - `apps/occupancy-service`: implements `BoardingObservation`, `BoardingAttribution`, `TripCapacity`, `OccupancyEstimate`, and `HistoricalCrowding` per `DES-01`.
- **Verification Criteria (`ticketing-tests.md` / `FR-050` / `FR-051` / `E2E-04`):**
  1. Single-line stop (`k = 1`) attributes `1.0` to the next departure.
  2. Shared multi-line stop with historical-demand weights splits `1.0` proportionally across candidate trips.
  3. Shared multi-line stop with missing history uses the `1 / k` equal-share fallback and marks `EQUAL_SHARE`.
  4. Exact `validated_at == effective_departure_at` vs `validated_at > effective_departure_at` boundary and cancelled trip exclusion behave deterministically.
  5. Duplicate/out-of-order `TicketValidated` deliveries never double-count; missing/stale capacity reports explicit status instead of `0`.

---

## 4. Consequences

### Positive
- Allows boarding-based occupancy estimation and capacity monitoring using fixed stop-entrance validators (`A-05`, `A-13`) without requiring onboard sensors or tap-out gates.
- Preserves privacy (`D-08`, `NFR-056`) by keeping `TicketValidated` events free of passenger/ticket identifiers.
- Prevents misleading UI or analytics claims by explicitly distinguishing stored `capacity`, estimated boardings, and derived available capacity alongside staleness metadata.

### Negative / Trade-offs
- Without alighting data, cumulative boarding counts across multi-stop trips reflect boarding demand rather than net onboard passengers after intermediate stops; as noted in `A-03`, estimates are primarily meaningful for relative crowding comparisons and peak-hour/busy-trip analysis.
- Cold-start deployments rely on the equal-share (`1 / k`) fallback until sufficient historical demand or configured line weights exist.
