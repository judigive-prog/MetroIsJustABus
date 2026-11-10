# DES-01 — Assumption register

Version 0.1, 2026-11-10. Every entry below is **Pending**: all fourteen Linear
decision issues were in Backlog when inspected. MET-169 does not approve them.
The working proposals are recorded to expose their impact on the design.

| Assumption / source | Question | Working proposal | Consequence for this model | Traceability |
|---|---|---|---|---|
| [A-01 / MET-154](https://linear.app/metroisjustabus-ase/issue/MET-154) | Schedule conditions | Day-of-week, holidays or special dates are the working scope. | Variant selection, precedence, overnight and DST representation remain provisional. | FR-006, FR-072, NFR-033 |
| [A-02 / MET-155](https://linear.app/metroisjustabus-ase/issue/MET-155) | Disruption source | Staff register delays/cancellations/diversions; a simulator uses the staff boundary; no GPS feed. | Keep source/author/history explicit; no telemetry entities invented. | FR-010–013, FR-090–096 |
| [A-03 / MET-156](https://linear.app/metroisjustabus-ase/issue/MET-156) | Boarding attribution | Stop-entrance validations are proposed to be split among candidate trips using historical demand, initially equal shares. | Document observation versus attribution. No chosen formula, weights or measured occupancy; attribution implementation waits. | FR-050–056 |
| [A-04 / MET-157](https://linear.app/metroisjustabus-ase/issue/MET-157) | Payment scope | A simulated provider is proposed. | SimulatedPayment remains a separate owner; no real payment or card-data model. | FR-032, FR-033, FR-037 |
| [A-05 / MET-158](https://linear.app/metroisjustabus-ase/issue/MET-158) | Validator device/API | A fixed entrance device plus validation API and simulator is proposed. | Validator ownership, credential binding and final input/time rules need feature review. | FR-040–047 |
| [A-06 / MET-159](https://linear.app/metroisjustabus-ase/issue/MET-159) | Notification channels | In-app plus an external simulated/sandboxed channel is proposed; the stack chooses sandbox email. | Channel/preferences/attempt model is extensible. Sandbox email is a team stack choice, not teacher approval. | FR-060–069 |
| [A-07 / MET-160](https://linear.app/metroisjustabus-ase/issue/MET-160) | Staff roles | One initial staff role is proposed with room for later splitting. | RoleAssignment is conceptual; staff provisioning and exact privileges require agreement. | FR-100, FR-101 |
| [A-08 / MET-161](https://linear.app/metroisjustabus-ase/issue/MET-161) | Ticket validity scope | Tickets are proposed to be network-wide unless their type specifies otherwise. | Do not assume permanent all-lines entitlement or introduce line/zone FKs before terms are agreed. | FR-030, FR-040–048 |
| [A-09 / MET-162](https://linear.app/metroisjustabus-ase/issue/MET-162) | History retention | Duration is unspecified; team must decide and document it. | No TTL, purge period or privacy-policy approval invented; deletion/anonymization and all historical tables depend on this. | FR-023, FR-103, NFR-056 |
| [A-10 / MET-163](https://linear.app/metroisjustabus-ase/issue/MET-163) | Network/load size | A mid-size network and later agreed load targets are proposed. | No capacity sizing, partitioning or benchmark threshold claimed by these logical models. | NFR-040–043 |
| [A-11 / MET-164](https://linear.app/metroisjustabus-ase/issue/MET-164) | Public expected crowding | Coarse historical crowding is proposed for visitors/passengers. | HistoricalCrowding remains derived; visibility and thresholds unresolved. | FR-009, FR-053, FR-056 |
| [A-12 / MET-165](https://linear.app/metroisjustabus-ase/issue/MET-165) | Transfers/refunds | Both are proposed out of scope. | No transfer/refund entity or lifecycle is added. Revisit purchase/ownership if scope changes. | FR-030–037 |
| [A-13 / MET-166](https://linear.app/metroisjustabus-ase/issue/MET-166) | Entrance validation | Validation before boarding at a stop/station, with no line/trip in the request, is proposed. | Presented ticket/validator/stop are distinct from estimated trip attribution; no per-line validation fact. | FR-040–047, FR-051 |
| [A-14 / MET-167](https://linear.app/metroisjustabus-ase/issue/MET-167) | Identity edits | Contact/preferences edits only; identity data edits are proposed out of scope. | Separate mutable contact profile from protected identity data; personal-ticket terms and account deletion require review. | FR-022, FR-023 |

## Additional model decisions to review

These are technical proposals uncovered while modeling, not new baseline
requirements or claims that the A-series decisions have been resolved.

1. RoutePattern and PatternStop distinguish line direction and repeated stop
   occurrences. Confirm the minimal route/direction representation.
2. ScheduledTrip versus TripOccurrence distinguishes recurring templates from
   dated runs. Agree stable IDs and whether subscriptions target either kind.
3. Define operational-state precedence for overlapping disruptions.
4. Confirm Validator ownership in ticketing and TripCapacity ownership in
   occupancy, including capacity defaults and historical changes.
5. Align terms_snapshot versus terms and reason versus cause across purchase
   code and preliminary validation design before validation implementation.
6. Define account-deletion/anonymization coordination without cross-service
   database access. No cascading deletion of issued/history records by default.

Record the reviewer, date, evidence, rationale and affected model/requirement
versions when a decision is accepted. An agent's consistency check is not team
or teaching-staff approval.
