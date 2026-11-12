# Ticket Validation — Review

**Status:** AI review done (2026-10-27). **Human review pending:** the team must confirm, change or reject each decision below and add its own findings before PL7. Decisions in the table are proposals by the AI assistant until a team member signs them off in the last column.

## 1. Review findings

| ID | Finding | Identified by | Decision | Justification | Confirmed by (team) |
|---|---|---|---|---|---|
| F-01 | FR-042 lists "unknown ticket" as a rejection reason, but conventions say missing resources return a 4xx. The two sources disagree on how an unknown ticket is answered | AI | Accept: `200 REJECTED UNKNOWN_TICKET` (D-06). Update conventions to name this exception | FR-042 is a requirement; conventions are a team rule and must yield or be updated (conventions header: "stop and ask which one to update"). A validator shows every refusal the same way | |
| F-02 | The statement says "record **successful** validations" (S-2). TV-REQ-08 also records rejected attempts, which is not stated | AI | Accept as a team decision, kept as Should | Supported by S-7 ("information about … validation activity") and FR-047 in v0.2, marked (A) there. Labelled D-07, not presented as stated | |
| F-03 | Design compared `ticketId` **and** `deviceTime` to detect key reuse. A validator that re-reads its clock on retry would get a false `409` and the passenger would be refused | AI (self-review of design) | Accept: compare `ticketId` only. Fixed in design §4, TV-REQ-06, new TV-AC-10b, TV-V03 | Device time is not used in the decision (D-02), so it cannot make two requests different | |
| F-04 | TV-REQ-03 first returned "the first reason in that order" as if the order were stated. The order is invented | AI | Accept: recorded as decision D-11 | PL6 rule: do not present invented rules as statement requirements | |
| F-05 | TV-AC-13 (device time ignored) was only covered by a unit test, which cannot see that the device time is stored | AI | Accept: added AC-13 to TV-V02 (integration) | Each scenario needs a test that observes its "Then" | |
| F-06 | "Journey" is undefined (S-4). An accidental double tap or a transfer consumes a second journey under D-05, which passengers may find unfair | AI | Defer: OQ-01, OQ-02; ask the lecturers | A business rule for the operator, not something to settle in code (principle 11) | |
| F-07 | Validator credentials have no named issuer (tech stack: "service credentials") | AI | Defer: OQ-03; PL7 uses dev-signed test tokens (TV-T04) | Needs a cross-feature decision in the tech stack | |
| | *Team: add at least one finding of your own here* | Human | | | |

## 2. Traceability matrix

| Project source or assumption | Requirement | Design element | Task | Acceptance criterion |
|---|---|---|---|---|
| S-1, S-2, A-05, A-13 | TV-REQ-01 | REST `POST /validations`; validator registry | T01, T04, T05 | AC-01: `200 ACCEPTED` with stop `S1` |
| S-3, S-4, FR-041, FR-048 | TV-REQ-02 | Pure evaluator, design §4 step 5; `terms` snapshot | T02 | AC-01, AC-05, AC-13 |
| FR-042, D-11 | TV-REQ-03 | Reason order in evaluator | T02 | AC-03, AC-06, AC-07, AC-08 |
| S-2, FR-043 | TV-REQ-04 | `validation_attempts` | T01, T03 | AC-01: one record with stop and time |
| FR-044, FR-035, D-04, D-05 | TV-REQ-05 | Ticket update and `ticket_state_changes` | T03 | AC-01, AC-02, AC-04 |
| S-5, FR-045, NFR-013 | TV-REQ-06 | Unique (`validator_id`, `idempotency_key`), stored response | T01, T03, T05 | AC-09, AC-10, AC-10b |
| S-3 "previous validations", FR-046, NFR-030 | TV-REQ-07 | `SELECT … FOR UPDATE` on ticket | T03 | AC-11: one ACCEPTED, one REJECTED |
| S-7, FR-047, D-07 | TV-REQ-08 | Rejected rows in `validation_attempts` | T03 | AC-03, AC-08: rejected record exists |
| S-6, NFR-015, D-08 | TV-REQ-09 | `outbox_event`, `TicketValidated` v1 | T03, T06 | AC-01: one event; AC-03: none |
| NFR-050, NFR-053 | TV-REQ-10 | Validator permission class | T04 | AC-14: 401 / 403 / 403 |
| S-3, FR-035 | TV-REQ-11 | Expiry branch, state change to `EXPIRED` | T02, T03 | AC-06 |
| NFR-020, principle 5 | TV-NFR-02 | No remote call in the request path | V02 | AC-12 |

Check: every requirement has a source or a labelled decision, a design element, an implementation task and a validation test. Gap: TV-NFR-01 (1 s target) has no task in PL7; deferred with OQ-06.

## 3. Testability challenge

**Requirement chosen:** TV-REQ-05 (an accepted validation updates the ticket). The AI was asked to derive three scenarios using only the requirement, the statement and decisions already recorded.

| # | Scenario | Expected outcome | Determinable? |
|---|---|---|---|
| 1 | 10-journey ticket in `ISSUED`, validated once | 9 left, `ACTIVE` | Yes, from TV-REQ-05 |
| 2 | 24 h pass activated at 08:00, validated again at 18:00 the same day | Accepted, period end unchanged | Yes, but only because of D-04 (period starts at first use). The statement alone does not say |
| 3 | 10-journey ticket validated at stop A, then 4 minutes later at stop B (a transfer) | ? | **Only with D-05.** The statement does not define a journey. Without D-05 the expected value of `remaining_journeys` (8 or 9) cannot be determined. Recorded as OQ-01 |

Outcome: the requirement is testable only together with D-04 and D-05. Both are now explicit decisions, and the transfer case stays open for the team.

## 4. Impact of input quality

Evidence from this project: the same feature appears in the project-wide specification generated from the statement alone (v0.1) and after the team supplied its own knowledge (v0.2).

| Aspect | v0.1 (input: statement only) | v0.2 / this spec (input: statement + team decisions) |
|---|---|---|
| Validation context | "time and trip; line and stop where applicable" (validator assumed inside the bus) | Ticket, validator and time; stop derived from the validator; no line or trip (A-13, D-03) |
| Staff queries | Filter by line and trip | Per-line statistics removed: the data does not exist |
| Occupancy link | Validations update "the relevant trip" | Boarding at a stop; attribution to trips is an open rule (A-03) |
| Decision time, retries with a new device time, concurrency details | Not addressed | D-02, F-03, TV-REQ-07 |

Lesson: with the statement alone the AI filled the gap about *where* validation happens with a plausible but wrong guess, and that guess spread to staff queries and occupancy. Adding one sentence of domain knowledge removed it everywhere.

*Optional for the team:* repeat the experiment at feature level by giving a fresh AI session only "Passengers validate tickets when boarding; the system says yes or no" and comparing the result with [requirements.md](requirements.md).

## 5. AI-use record

| Item | Record |
|---|---|
| Tool / model | Claude Code (desktop app), model `claude-opus-5-5` |
| Date | 2026-10-27 |
| Inputs given | PL6 handout; project statement v1.0; requirements specification v0.2 and v0.1 with review comments; `.ai/steering/*.md` |
| Representative instruction | "можешь сделать пл6?" (can you do PL6?), after the AI recommended ticket validation as the feature and the user accepted |
| What the AI produced | Feature choice rationale, requirements.md, design.md, tasks.md, this review (findings F-01 to F-07, matrix, testability challenge) |
| Corrections made by the AI in self-review | F-03 (false 409 on retry), F-04 (invented rule shown as stated), F-05 (missing integration coverage) |
| Human decisions | **Pending.** To be recorded here: who reviewed, which proposed decisions (D-02 to D-11) were accepted or changed, and time spent |
