# NFR-005 — Review and evidence

Version: 0.1 draft, 2026-11-11.
Issue: [MET-87](https://linear.app/metroisjustabus-ase/issue/MET-87).
Baseline: `969079ee45712a147cbab74a60f899b415efa02e`.
Status: draft prepared; human review and acceptance pending.

## Acceptance evidence

| MET-87 criterion | Prepared evidence | Status |
|---|---|---|
| Identify responsibilities, owned data and external interfaces | [Design sections 2–3](design.md#2-architecture-and-responsibilities); linked MET-169 entity model | Draft prepared |
| Justify boundaries, including independent notification, and trade-offs | Design sections 2, 4 and 5; alternatives include monolithic backend, inline notification, shared DB and synchronous occupancy | Draft prepared; team acceptance pending |
| Link domain/data and behavioural models to responsibilities/interfaces | Design sections 1 and 4 link the domain, purchase and validation models; disruption/notification summary and MET-170 handoff are explicit | Draft prepared; detailed future models remain pending |
| Link evidence and record limitations before completion | This review, source paths and design section 6 | Local document checks recorded below; PR, human review and acceptance pending |

MET-169 remains the completion prerequisite. Its
[review record](../domain-data-ownership/review.md) and
[PR #3](https://github.com/judigive-prog/MetroIsJustABus/pull/3) record pending
team review. Drafting this dependent design is allowed; an issue marked Done
does not substitute for the missing acceptance evidence. No Linear status was
changed by this work.

## Existing source versus intended architecture

Paths below are relative to the repository root. File presence and static
inspection are evidence of source only, not executed acceptance tests.

| Observation at baseline | Source evidence | Consequence |
|---|---|---|
| Ticketing and payment-sim source directories exist; web/core/occupancy/notification and deployment definitions are absent from the tracked inventory | `apps/ticketing-service/`, `simulators/payment-sim/`, `.ai/steering/tech-stack.md` | Full architecture diagram is a target, not an operational system |
| Ticketing has ticket-type and purchase routes; validation routes are absent | `apps/ticketing-service/config/urls.py`, `ticket_types/api/urls.py`, `purchases/api/urls.py` beneath that service | Do not describe validation APIs as implemented |
| Purchase persists an outbox intent inside the completion transaction; an uncertain payment schedules future retry metadata | `apps/ticketing-service/purchases/services.py`, `apps/ticketing-service/outbox/services.py` | Local transaction structure is present; no completed reconciler/relay or recovery claim |
| `TicketPurchasedV1` source model exists | `packages/metro_common/metro_common/events/ticket_purchased.py` | No committed `contracts/` directory or deployed consumer evidence; MET-88 must establish contract artefacts |
| Ticketing verifies JWTs using a configured public key file; JWKS fetching/cache is explicitly unimplemented | `apps/ticketing-service/common/auth.py` | Adopted JWKS architecture and current implementation must remain distinct |
| Payment HTTP wrapper performs one attempt with connection/read timeouts | `apps/ticketing-service/common/http.py`, `apps/ticketing-service/purchases/clients.py` | Generic steering retry policy is not evidence of implemented retries; uncertain purchase reconciliation remains separate |
| Review files contain unconfirmed feature decisions and differing ticket snapshot/state-change vocabulary | `../domain-data-ownership/design.md`, `../ticket-validation/review.md`, `../ticket-purchase/review.md` | MET-87 preserves ownership and links the findings; it does not silently rewrite feature rules |

## Open review findings

| ID | Finding / required decision | Follow-up |
|---|---|---|
| CB-01 | Confirm proposed Validator ownership in ticketing and TripCapacity in occupancy | MET-169 review plus NFR-032; no model changes here |
| CB-02 | A-03 attribution, A-06 channels, A-05/A-13 validator context and related A-series decisions remain unresolved | Use the linked assumption register; do not choose rules in implementation |
| CB-03 | Route patterns, dated trip identity, subscription target semantics and disruption overlap precedence affect event scope | Agree model identities/rules before MET-88 freezes those contracts |
| CB-04 | JWT claims, key rotation/cache, role freshness, service credential issuance and minimized contact access need explicit agreements | Security and API contract work; fail closed on unverifiable identity |
| CB-05 | Consumer bootstrap, gap recovery and effective-time histories need explicit interfaces and verification | MET-88/MET-170 and corresponding features; no hidden callback or DB join |
| CB-06 | Current CI triggers PR checks for `main`, while this branch is based on the unmerged MET-169 | At PR preparation, account for the team's stacked-PR workflow and obtain relevant CI evidence; no workflow change here |

No finding above is an automatic approval request or a new blocker preventing
this draft. Decisions that change business behaviour remain pending for the
team; deployment and detailed contracts belong to subsequent work.

## Verification and review record

This change adds documentation only. Local verification checks relative links,
required design topics and Git whitespace errors. It does not exercise runtime
behaviour; service, integration, failure and deployment results are Pending.

| Check / reviewer | Result |
|---|---|
| Local relative Markdown links | Passed on 2026-11-11: 15 relative links checked across both documents, including heading anchors |
| Required design topics and whitespace | Passed on 2026-11-11: component/decision coverage and closed code fences checked; new-file whitespace checked with `git diff --no-index --check` against `/dev/null` |
| Agent consistency review against inspected model/steering/source | Prepared; unresolved decisions and source/target differences recorded above |
| Human architecture review: reviewer/date/findings/decision | Pending |
| Accepted version and rationale | Pending |
| MET-87 commit/PR and CI evidence | Pending |

## AI contribution record

Codex prepared `design.md` and this review on 2026-11-11 using the sources
listed above and the MET-87 issue. No domain code, migrations, contracts,
steering rules or CI configuration changed. Human edits/review time remain
unrecorded until actually supplied. No commit, push, PR creation or merge was
performed as part of preparing this draft.
