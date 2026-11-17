# Ticketing and Validation Service test coverage

The [Linear component view](https://linear.app/metroisjustabus-ase/team/MET/issue-label/ticketing%20and%20validation%20service) is the source for the 41 issue IDs below. The [purchase scenarios](ticket-purchase/requirements.md#8-acceptance-scenarios) and [validation test tasks](ticket-validation/tasks.md#validation-tasks) define the detailed acceptance cases.

## Run the suites

CI runs each suite in its own environment with Python 3.13. The ticketing suite uses PostgreSQL, including the concurrent purchase test. The payment simulator uses its SQLite backend. Both use Django's test databases. Use disposable database credentials and test-only secret files. The [CI jobs](../../../.github/workflows/ci.yml) list the environment variables for each service.

Run from the repository root after preparing those environment variables:

```sh
uv run --locked --directory apps/ticketing-service --group contracts --with pytest --with pytest-django pytest --no-migrations
uv run --locked --directory simulators/payment-sim --with pytest --with pytest-django pytest --no-migrations
```

Use `-m unit` for the ticketing HTTP client tests without connecting to PostgreSQL. The applications currently have models and empty migration packages. `--no-migrations` creates the test tables from the models. Once the application migrations are committed, run these suites through the migrations and remove the flag from the commands and CI.

## Linear issues and acceptance cases

**Automated** means an executable case exercises the current service behavior. **Partial** lists what runs and what remains. **Planned** records the acceptance case for an unimplemented flow. **Decision** records evidence to gather when the team confirms the assumption.

| Linear | Requirement | Status | Verification |
| --- | --- | --- | --- |
| MET-24 | FR-030 | Partial | Seed and list two offers with different prices and conditions. Add validity periods, usage rules and journey-limit fixtures when the rule model exists. |
| MET-25 | FR-031 | Automated | The public catalogue exposes prices and conditions, excludes retired types and returns the next page by cursor. |
| MET-26 | FR-032 | Automated | Buy an active offer. Check the issued ticket and reject unknown, retired and repriced offers before contacting payment. |
| MET-27 | FR-033 | Automated | Replay completion after retirement, reject changed payloads under the same key and race ten requests on PostgreSQL. Assert one purchase, ticket, state change and outbox event. |
| MET-28 | FR-034 | Planned | Seed two passengers, tickets and validation attempts. Assert each passenger sees only their tickets and their own newest-first history. |
| MET-29 | FR-035 | Partial | Assert one purchase-to-issued history record. Exercise subsequent lifecycle transitions and verify append-only storage once implemented. |
| MET-30 | FR-036 | Partial | Read PENDING via GET, explicitly finalize the purchase and read COMPLETED. Exercise the reconciler and asynchronous notification once wired. |
| MET-31 | FR-037 | Partial | Exercise simulator approval, decline, slow response, transient error and replay through its API. Verify the HTTP client and pending behavior on uncertain payment. Add the live cross-service recovery scenario when the reconciler is available. |
| MET-32 | FR-040 | Planned | An authenticated validator submits a ticket, validator and use time. Resolve the stop and exercise missing and unknown inputs under the agreed API. |
| MET-33 | FR-041 | Planned | Evaluate validity from rules, ticket state and usage history with a fixed clock. Cover expiry and exhausted journeys. |
| MET-34 | FR-042 | Planned | Return a reason for a rejected validation. Verify that rejection leaves entitlement unchanged. |
| MET-35 | FR-043 | Planned | Accept a valid tap and persist the validation record with the agreed stop, device and timestamp fields. |
| MET-36 | FR-044 | Planned | Accept a validation and assert the state change and remaining journeys are consistent with the validated ticket type. |
| MET-37 | FR-045 | Planned | Replay the same validator request and assert one validation record and one entitlement change. |
| MET-38 | FR-046 | Planned | Race distinct requests for the last journey on PostgreSQL. Assert one acceptance and no negative entitlement. |
| MET-39 | FR-047 | Planned | Reject a validation and verify an audit record exists while the ticket and success-event outbox stay unchanged. |
| MET-40 | FR-048 | Planned | Configure validity rules for two types and verify their differing results and boundary times under the approved rule table. |
| MET-42 | FR-051 | Planned | Deliver a successful validation for a shared stop. Verify estimated boarding attribution across candidate trips and the fallback for missing history. |
| MET-65 | FR-080 | Planned | Create, edit and retire a ticket type through the staff API. Verify status, audit and catalogue visibility. |
| MET-66 | FR-081 | Partial | Change a type during PENDING and verify issuance keeps the original terms and price. Add a staff-API regression once that API exists. |
| MET-67 | FR-082 | Planned | Seed usage and validation records across several dates and outcomes. Exercise each supported filter and verify matching results. |
| MET-68 | FR-083 | Planned | Compare the staff boarding and ticket-sales indicators with independently counted fixture records over the same time window. |
| MET-69 | FR-084 | Planned | Verify a staff support lookup can find a ticket and its validation history. Check authorization and record visibility. |
| MET-78 | FR-101 | Planned | Call each staff endpoint as unauthenticated, passenger and staff identities. Verify only authorized staff can act. |
| MET-79 | FR-102 | Partial | Verify another passenger's purchase returns 404 and each passenger has their own idempotency scope. Extend the isolation checks to tickets and validation history. |
| MET-92 | NFR-013 | Partial | Retry purchases and simulated charges, including timeouts and transient errors. Add validation and broker redelivery cases once the consumers exist. |
| MET-98 | NFR-022 | Partial | Inject an outbox write failure and verify transactional rollback and a single issuance on retry. Add connection-loss and message redelivery cases across components. |
| MET-102 | NFR-026 | Planned | Once a target and observation window are agreed, measure availability with the agreed health probes and dependency disruptions. |
| MET-104 | NFR-030 | Planned | Observe the ticket and validation from separate PostgreSQL connections during success, rollback and concurrent use. Verify committed state and its record agree. |
| MET-109 | NFR-041 | Planned | Measure validation latency under the agreed workload and compare it to the approved metric and threshold. |
| MET-156 | A-03 | Decision | Record expected allocations for shared stops, departure boundaries and missing history, then use those cases for FR-051. |
| MET-157 | A-04 | Decision | Confirm simulator outcomes and scope. Match approval, decline, retry and delayed-response expectations to the executable simulator suite. |
| MET-158 | A-05 | Decision | Confirm the validator interface and device model. Capture an accepted request and a rejected request through the agreed simulator. |
| MET-161 | A-08 | Decision | Confirm network-wide validity. Exercise the same type at validators on different lines under equivalent ticket state. |
| MET-165 | A-12 | Decision | Record the agreed scope for transfers and refunds, then verify the public interface matches that decision. |
| MET-166 | A-13 | Decision | Confirm the entrance validation context. Use a shared-stop fixture to verify a request can be resolved without line or trip IDs. |
| MET-179 | E2E-02 | Partial | Purchase API and simulator scenarios run independently. Add registration, live purchase and account ticket views against the full stack. |
| MET-180 | E2E-03 | Planned | From the validator simulator, exercise accepted and rejected taps, retry, and concurrent use. Check ticket state and the recorded history. |
| MET-181 | E2E-04 | Planned | Validate a boarding and verify how its attributed trip estimates appear in passenger and staff capacity views. |
| MET-184 | E2E-07 | Partial | Verify purchase ownership and reject staff-only tokens on the passenger purchase API. Add cross-component staff operations and account isolation. |
| MET-185 | E2E-08 | Partial | Verify issuance preserves terms after changing a type at the ORM boundary. Add staff edits and historical records through the actual staff workflows. |
