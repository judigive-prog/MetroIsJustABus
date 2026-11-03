# Review — Ticket Purchase with Simulated Payment

**Status:** AI-prepared first pass. The "Decision" column holds a **proposed** decision. The team must confirm, change or reject each one in class; a proposal is not a team decision until then. Add the findings your team finds by hand (at least one row marked *Human* is expected).

## 1. Review findings and decisions

| # | Finding | Identified by | Decision (proposed) | Justification / evidence |
|---|---|---|---|---|
| F-01 | The project statement never mentions payment, purchase pricing or refunds. It only says passengers "acquire tickets". The simulated payment step, its outcomes and "no refunds" come from `product.md`/`tech-stack.md`. | AI (verified by searching the extracted statement text for "payment" and "purchase": no hits) | **Accept** — keep payment, but label it a team decision [P] | Handout: do not present invented rules as statement requirements. `requirements.md` §2 and tags make the distinction explicit. |
| F-02 | `conventions.md` says a down dependency returns 503, but a purchase whose payment outcome is unknown already exists and is `PENDING`; "503" would hide a possible charge, "202 PENDING" tells the truth. | AI | **Defer** → OQ-01, with recommendation: 202 once a purchase is recorded, 503 only when nothing was recorded | `conventions.md` §Calls ("When a dependency is down, return 503") vs. §API ("transient dependency failure must not become a permanently replayed terminal result", "uncertain payment outcome stays pending"). The conventions file says to ask which document to update when they conflict. |
| F-03 | A background reconciler is needed to satisfy principle 3 ("never left half-done"), but `tech-stack.md` lists only API, relay and consumer roles. Lazy reconciliation on client retry cannot finish a purchase the client abandons. | AI | **Defer** → OQ-02; recommendation: add the role | Principle 3; `tech-stack.md` "deployment roles" paragraph. |
| F-04 | `payment-sim` is drawn with no storage, but an idempotent simulator that forgets keys on restart would charge twice after a restart, invalidating the failure tests. Its route namespace is also missing from the conventions' service list. | AI | **Defer** → OQ-03; recommendation: SQLite on a named volume, `/api/payment-sim/v1/payments` | tech-stack diagram vs. design §5.2; PUR-NFR-01, AS-07. |
| F-05 | Naive order "validate the ticket type, then check the idempotency key" breaks replay: after a type is retired, a legitimate retry would get 422 instead of the original 201. | AI | **Accept** — look up the key first (D-07, PUR-FR-16, AS-13) | Reasoning from the state machine; covered by acceptance scenario AS-13 so it is testable. |
| F-06 | `AGENTS.md` uploaded empty (0 bytes); `tech-stack.md` and `tech-stack_1.md` are byte-identical. | AI | **Accept** — task T-01 | `wc -c` and `diff` on the uploaded files. Without `AGENTS.md`, agents in PL7 have no project rules file. |
| F-07 | Steering files cite FR/NFR IDs from "requirements specification v0.2" that was not provided, so those references could not be verified. | AI | **Defer** → OQ-04; feature-local IDs used, cited IDs shown as unverified | Cannot confirm FR-033 etc. exist or mean what the steering files say. |
| F-08 | The convention "redeliver the same event and assert one effect" needs a consumer; this feature only produces `TicketPurchased`. | AI | **Accept** deferral (T-31); test relay duplicate publication with the same `eventId` instead (T-24) | `conventions.md` §Tests; principle 12 (uncertain scope → out). |
| F-09 | Verifying the JWT needs core-backend's public key. If JWKS is unreachable and the cache is cold, a purchase fails because of an unrelated component. | AI | **Defer** → OQ-06; recommendation: cache with TTL | Statement: failure of one part "should not unnecessarily make the entire system unavailable". |
| F-10 | If a client gives up after the purchase row is created, the reconciler may still complete it, issuing a ticket the passenger did not wait for. | AI | **Defer / accept risk** → OQ-05 | Consequence of D-12 (never auto-fail a `PENDING`); the alternative could contradict a real approval. No refunds exist to repair it. |
| F-11 | During the AI's own consistency pass, `AMB-10` referenced a decision `D-13` that was missing from the decisions table, and `AS-14` used two different error codes where the design says one. | AI (self-review) | **Accept** — both corrected in `requirements.md` | Cross-reading the three artifacts. |
| F-12 | *(Team to add)* Human-identified finding. | Human | — | — |

## 2. Traceability matrix

Legend: **S-n** = statement passage (requirements §2), **P** = steering file decision, **D-n** = decision in this spec. Task IDs from `tasks.md`.

| Project source or documented assumption | Requirement ID | Design element | Task ID | Acceptance criterion |
|---|---|---|---|---|
| S-1, D-01 | PUR-FR-01 | `GET ticket-types`, `ticket_types` table (§3, §5.1) | T-04, T-09 | Only active types listed (T-09 endpoint tests) |
| S-1, S-2, D-02 | PUR-FR-02 | Create purchase (§6.1), `purchases` | T-08, T-09 | AS-01 |
| S-3, P (conventions) | PUR-FR-03 | Header validation (§6.1 step 2) | T-09 | AS-14 |
| S-3, S-6, P | PUR-FR-04 | Key lookup, stored response (§6.1 step 3), `uq_purchases_passenger_key` | T-04, T-08 | AS-02, AS-04 |
| P (conventions) | PUR-FR-05 | Fingerprint comparison (§3, §6.1) | T-08 | AS-03 |
| S-1, P (principle 7) | PUR-FR-06 | `terms_snapshot` on purchase and ticket (§3, §6.2) | T-04, T-08 | AS-01 (terms equal snapshot), AS-12 |
| D-04 (principle 9) | PUR-FR-07 | Price check (§6.1 step 4) | T-08 | AS-11 |
| P, D-05 | PUR-FR-08 | `clients.pay`, payment-sim API (§5.2) | T-06, T-07 | AS-01, AS-05, AS-06, AS-07 (via T-22) |
| S-3, S-7, P (principles 1–3) | PUR-FR-09 | Finalize transaction (§6.2) | T-08 | AS-01, AS-08 |
| D-06 | PUR-FR-10 | `finalize_declined` | T-08 | AS-05 |
| S-5, P | PUR-FR-11 | Uncertain-result handling (§6.1 step 7), failure matrix (§8) | T-07, T-08 | AS-06, AS-07, AS-09 |
| S-7, P (principle 3) | PUR-FR-12 | Reconciler (§6.3) | T-10 | AS-06, AS-07, AS-08 |
| S-2, P (principle 6) | PUR-FR-13 | Owner-only selector, 404 (§9) | T-02, T-09 | AS-15 |
| P (principle 6), D-08 | PUR-FR-14 | `IsPassenger` permission | T-02 | AS-15 |
| S-8, P | PUR-FR-15 | `TicketPurchased` event (§5.3), outbox | T-05, T-08 | AS-16, AS-17 |
| D-07 | PUR-FR-16 | Lookup-before-validate ordering (§6.1) | T-08 | AS-10, AS-13 |
| P (principles 3, 7) | PUR-FR-17 | Issue from snapshot, not live type (§6.2) | T-08 | AS-12 |
| S-3, P (principle 2) | PUR-NFR-01 | Unique constraints, row lock (§3, §6.2) | T-04, T-21 | AS-04 |
| S-4, P (principle 5) | PUR-NFR-02 | Outbox, no broker call in request (§1, §6.2) | T-05, T-24 | AS-16 |
| S-5, P (conventions) | PUR-NFR-03 | HTTP client wrapper timeouts | T-03, T-07 | AS-06 |
| P (conventions) | PUR-NFR-04 | Exception handler, error shape | T-03, T-27 | AS-18 |
| P (conventions) | PUR-NFR-05 | structlog + redaction | T-03, T-27 | AS-18 |
| P (tech-stack) | PUR-NFR-06 | OpenAPI/event schema drift checks | T-11, T-25 | AS-17 |
| P (conventions) | PUR-NFR-07 | `*_cents` + currency columns | T-04 | T-04 constraint tests |
| P (conventions) | PUR-NFR-08 | `@pytest.mark.req` | T-29 | Generated matrix complete |
| P (product.md) | PUR-NFR-09 | Opaque token only | T-06, T-27 | AS-18 (canary token not in logs) |
| — | PUR-NFR-10 | No target asserted | T-32 (deferred) | n/a (OQ-08) |

**Coverage check done by the AI:** every requirement has a source (statement passage, steering file, or a decision in `requirements.md` §5), a design element, at least one task and an acceptance criterion, except PUR-NFR-10 which is deliberately a "no target" statement. Items still blocked by open questions: PUR-FR-11 status code (OQ-01), reconciler deployment (OQ-02), payment-sim tasks T-06/T-07 (OQ-03). The team must re-check this matrix after resolving T-00.

## 3. Testability challenge

**Requirement chosen:** PUR-FR-11 — *If the payment outcome is not definitively known, the purchase stays `PENDING`, no ticket is issued, and the response indicates pending state; never an invented success or failure.*

Three scenarios derived without adding business rules (all use only rules already in `requirements.md`):

| # | Given | When | Then |
|---|---|---|---|
| TC-1 | Active type, passenger, token `sim_slow` (sim responds after the 3 s read timeout) | POST purchase | 202 with `status: PENDING`, tickets 0, outbox 0; `GET /purchases/{id}` shows `PENDING`. |
| TC-2 | Token `sim_error` (sim returns 500 and records nothing) | POST purchase | 202 `PENDING`, tickets 0; sim `chargeCount` is 0 for the key; the purchase is later completed by reconciliation. |
| TC-3 | Token `sim_lose_response` (sim records approval, drops connection) | POST purchase, then the same request again with the same key | First: 202 `PENDING`. Replay: still `PENDING` or `COMPLETED` (never a second purchase); tickets ≤ 1, sim `chargeCount` is exactly 1. |

**Result:** expected outcomes could be determined for all three. Two points needed clarification, which is the value of the exercise:
1. The wording "eventually completes" has no time bound. A bound would be a new rule, so none was invented. The tests set a short reconciler backoff through configuration and poll with a timeout; production values stay tunable (OQ-08).
2. The exact status code "202" depends on OQ-01. Until the team resolves it, tests assert "pending state in the body and no ticket", and the status code assertion is isolated in one place.

## 4. Input quality note (AI observation, not an experiment)

The handout asks the team to compare a specification generated from a vague input with one from an improved input. This pass did **not** run that experiment: the team should run it for real and record it here. What the AI observed while preparing this pass:

- Generating from the *statement alone* would have produced no payment step, no pending state and no reconciliation, because the statement says only "acquire tickets". Those came entirely from the steering files, so a spec built from the statement alone would silently drop the hardest requirement of this feature.
- Generating from the one-line description "buy a ticket with simulated payment" would invite exactly the unsupported assumptions the handout warns about (card fields, refunds, quantities, receipts, e-mail confirmation). Each of these was instead listed as an explicit decision, an out-of-scope item or an open question.
- Missing context (empty `AGENTS.md`, unavailable spec v0.2) produced unverifiable references; they are marked unverified rather than guessed.

## 5. AI-use record (team to complete)

| Item | Record |
|---|---|
| Tool / model | Claude (claude.ai chat), model Claude Sonnet 5.5 |
| Inputs given | `pl6.pdf` handout; `product.md`, `tech-stack.md`, `conventions.md`, `principles.md`; project statement PDF; `AGENTS.md` (empty). Spec v0.2 not available. |
| Representative instructions | (1) "I want to do ticket purchase with simulated payment." (2) Handout instructions: separate stated requirements, team decisions and unresolved questions; produce `requirements.md`, `design.md`, `tasks.md`, `review.md`. *Team: add the exact prompts you used.* |
| AI-found corrections | F-11 (D-13 missing; AS-14 error code mismatch), applied before delivery. |
| Human review | *Team: record who reviewed which artifact, time spent, edits made, and set `Human-Intervention: none \| edited \| rewritten`.* |
| Not yet verified by a human | Every decision D-01..D-13, every proposed open-question recommendation, the data model and constraint names, and the claim that the statement contains no payment requirement (re-check against the PDF). |
