# ADR A-04 - Simulated payment scope

| Field | Record |
| --- | --- |
| Linear issue | [MET-157 - Confirm simulated payment scope](https://linear.app/metroisjustabus-ase/issue/MET-157/a-04-confirm-simulated-payment-scope) |
| Status | Accepted in the team-reviewed requirements v0.2, recorded here |
| Decision baseline | 1 October 2026 |
| Record date | 19 November 2026 |
| Decision evidence | Requirements Specification v0.2, section 7, PDF page 19, tickets/purchase/payment review row |
| Direct requirements | FR-032, FR-033, FR-036, FR-037 |
| Related requirements | NFR-012, NFR-013, NFR-015, NFR-022, NFR-025, NFR-056, NFR-085 |

## Context and source review

The original course brief v1.0, dated 29 September 2026, requires passengers to acquire tickets and consult their account-associated tickets on PDF page 7. Its integration requirements on pages 8-9 cover component interfaces, temporary failures, retries, duplicate operations and consistency. These sections leave the payment mechanism and a real payment provider unspecified.

The team specification v0.2, dated 1 October 2026, introduces FR-037 as Should with source (A). PDF page 3 permits a simulated provider. Its assumption A-04 on page 16 selects simulation. Section 7 on page 19 records the discussion of tickets, purchase and payment, including Judit's and Egor's review comments, and the resulting decision, "Kept. Payment stays simulated (A-04)."

This record consolidates that existing team decision. The purchase feature also identifies N-05, N-06, N-09 and N-11 as approved decisions governing simulated payment retries, outcomes and failure modes. References are in [purchase requirements](../../sdd/specs/ticket-purchase/requirements.md#51-approved-by-the-team-n).

The inspected source files are identified for reproducible review:

| Source | Relevant PDF pages | SHA-256 |
| --- | --- | --- |
| `Automated_Software_Development_Project_Complete.v1.0.pdf` | 3-4 and 7-9 | `f96d2476611e32122b35406762fb58a886a0054482b57e91f7a662a9d8bd95a3` |
| `automated_software_engineering_v0.2 (2).pdf` | 3, 16 and 19 | `87e31ab4517b309cc4622e7deb9affa675e11044c8d04fc9a44f2cba3035d635` |

The source review distinguishes ticket acquisition required by the course brief from the simulated payment step introduced by the team's FR-037. FR-037 keeps its recorded Should priority.

## Decision

Use the project's simulated payment provider for ticket purchases in the course-project system, including its tests, demonstration and final project deployment.

The provider exchanges synthetic outcomes and identifiers with ticketing. The payment method is an opaque simulation token. Card collection, bank connections, merchant accounts, real financial credentials and movement of money are outside A-04's adopted scope.

Ticketing issues a ticket after an explicit simulated approval. A definitive decline produces the failed purchase outcome. A timeout, connection failure or ambiguous provider response preserves an uncertain purchase for recovery, following N-06. Payment retries carry the same purchase-derived idempotency key under N-05.

Payment identifiers and charge counters describe simulator state. They are evidence for purchase correctness and duplicate-effect tests.

## Rationale and alternatives

Simulation exercises the cross-component purchase boundary, retry safety and partial-failure behavior required by the project. Reserved tokens provide reproducible approval, decline, delay and transient-failure cases.

| Alternative | Assessment |
| --- | --- |
| Simulated provider | Adopted in the reviewed v0.2 decision and supported by the existing purchase architecture |
| Real payment provider | Adds financial integration and credentials beyond the payment scope selected in v0.2 |
| Omit the payment step | Would leave the team's FR-037 and its approved purchase flow uncovered |

## Impact on components and requirements

| Area | Impact |
| --- | --- |
| FR-032, FR-033 | Purchase and ticket issuance retain the confirmed simulated payment reference and guards against duplicate issuance |
| FR-036 | Confirmation reflects the actual purchase outcome, including a purchase completed after an uncertain payment |
| FR-037 | The payment step uses the simulator selected by A-04 |
| Ticketing and Validation Service | Owns purchases, ticket issuance and recovery of uncertain purchases |
| Simulators | `payment-sim` owns its simulated payment records and repeat-request behavior |
| Web Application | Presents the simulated payment and purchase outcome using the agreed API |
| NFR-012, NFR-013, NFR-015, NFR-022 | Payment timeouts, retries, duplicate prevention and recovery remain acceptance concerns |
| NFR-025, NFR-085 | Deterministic simulator scenarios supply controlled failure inputs |
| NFR-056 | Use synthetic payment tokens and exclude token values from passenger responses and logs |

The payment interface is described by the existing [OpenAPI contract](../../../contracts/openapi/payment-sim.v1.json). The [purchase design](../../sdd/specs/ticket-purchase/design.md) defines the owning transaction boundaries and event handoff.

## Implementation and verification evidence

Current behavior is inspected in [payment-sim services](../../../simulators/payment-sim/payments/services.py), the [ticketing payment client](../../../apps/ticketing-service/purchases/clients.py) and their existing tests.

| Scenario | Current simulator behavior | Existing verification |
| --- | --- | --- |
| `sim_approve` and same-key replay | Approved outcome, one simulated charge, same payment identifier | `test_same_key_replays_one_charge_and_different_payload_conflicts` |
| `sim_decline` or an unknown token | Declined outcome and zero simulated charges | `test_declined_payment_has_no_charge` |
| `sim_slow` | Approval is stored before the delayed response, with immediate same-key replay | `test_slow_approval_is_recorded_before_response_and_retry_has_no_delay` |
| `sim_error` | First request stores ERRORED with zero charges and returns 500, then same-key replay approves once | `test_transient_error_can_replay_and_charge_once` |
| Unauthenticated provider call | Refused before processing payment | `test_payment_requires_service_token` |
| HTTP payment boundary | Synthetic request, service authorization, idempotency key and correlation identifier are propagated | `test_payment_http_client_sends_simulator_contract_and_correlation_id` |
| Connection error or timeout | Ticketing classifies the result as UNCERTAIN after one request attempt | `test_payment_transport_failure_is_uncertain_after_one_attempt` |

The first five cases are in [payment-sim API tests](../../../simulators/payment-sim/payments/tests/test_payment_api.py). The last two are in [payment-client tests](../../../apps/ticketing-service/purchases/tests/test_payment_client.py).

The existing checks were executed on 19 November 2026 with Python 3.13.14, the locked service dependencies and synthetic test settings:

| Command from the repository root | Observed result |
| --- | --- |
| `uv run --offline --locked --directory simulators/payment-sim --with pytest --with pytest-django --python 3.13 pytest --no-migrations payments/tests/test_payment_api.py -q` | 7 passed, simulator SQLite test database |
| `uv run --offline --locked --directory apps/ticketing-service --group contracts --with pytest --with pytest-django --python 3.13 pytest purchases/tests/test_payment_client.py -m unit -q` | 3 passed, mocked HTTP transport |

Test environment variable names and secret-file setup are recorded in the existing [CI test jobs](../../../.github/workflows/ci.yml).

Two implementation limits are relevant to downstream acceptance:

- `sim_lose_response` currently returns 501 and records nothing. The design's approved-payment/lost-response recovery scenario still needs implementation and verification under MET-31.
- The simulator and client checks exercise local boundaries. Live cross-component recovery and final deployment evidence belong to the purchase implementation and release checks.

MET-31 and [MET-187](https://linear.app/metroisjustabus-ase/issue/MET-187/rel-01-review-the-final-release-candidate-and-requirement-coverage) can use this record as A-04 scope evidence. Their implementation and release criteria require their own verification.
