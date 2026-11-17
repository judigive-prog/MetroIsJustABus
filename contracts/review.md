# MET-88 / NFR-006 — Local evidence and review

Date: 2026-11-11. Status: prepared for team review, not accepted or merged.
Baseline: MET-87 commit `295ad30004f3f3c27bcc0858919f12083f2c5639`.
Issue: [MET-88](https://linear.app/metroisjustabus-ase/issue/MET-88).
Prerequisite: MET-87 / [PR #11](https://github.com/judigive-prog/MetroIsJustABus/pull/11).

## Acceptance mapping

| Criterion | Prepared evidence | Limit |
|---|---|---|
| Machine-readable, versioned HTTP and event contracts | Two OpenAPI 1.0.0 documents; TicketPurchased v1 JSON Schema and publisher AsyncAPI 1.0.0 document | Covers existing source; future APIs/events remain pending |
| Examples or automated representative checks | Synthetic HTTP/event examples, schema validation, drift checks and CI contract job | CI execution not observed; local results below |
| One synchronous request and one asynchronous event with versions, exchanged data and boundary validation | Actual ticketing client/provider HTTP boundary in separate environments; actual event builder/schema-only receiver probe with printed exchanged event | Payment operation stubbed; no notification implementation, broker transport or released-version compatibility claim |

## Observed local results

The student executed each generator and each boundary/example validator and
pasted the successful output in this chat. Codex also repeated the final checks
with locked dependencies after formatting and adding the CI job.

| Verification | Observed result |
|---|---|
| TicketPurchased example/schema cases | 9 passed: valid example, additive fields, required field, discriminators, types and formats |
| Real ticketing client / payment-sim view | 4 passed: approval, decline, additive response field, missing currency rejected |
| Existing event producer / isolated schema receiver | 3 passed: valid producer event, additive payload field, unsupported version rejected |
| AsyncAPI validation | 4 groups passed: official structure/checksum, 3 internal refs, metadata/schema coherence, example/correlation coherence |
| Generation drift | Event JSON Schema, AsyncAPI and both OpenAPI documents passed |
| Lockfile freshness | All three uv.lock files match their project declarations |
| Ruff | Lint passed; format check passed across 94 Python files (ruff 0.17.4) |
| Git whitespace | Passed |
| GitHub CI execution / human review / accepted version | Pending |

Representative producer exchange: event ID
`5486994f-c528-5a81-9805-ca3b0f2c8be8`, type `TicketPurchased`, version `1`,
producer `ticketing-service`, correlation `met-88-contract-example`.
Payload matches [the synthetic fixture](examples/ticket-purchased.v1.json).
The schema-only fixture's event ID is intentionally a different valid synthetic
UUID; the boundary check uses the producer's deterministic event ID.
The payment example records provider contract version `1.0.0` and synthetic
request/response data in [payment.v1.json](examples/payment.v1.json).

Python 3.13.18, uv 0.13.7, Django 5.2.19, DRF 3.18.3,
drf-spectacular 0.30.0, Pydantic 2.14.3 and jsonschema 4.26.0 were observed
locally; exact dependency versions/hashes are retained in each lockfile.
The original assignment PDFs were not independently inspected for this change;
requirement interpretation follows Linear and repository sources.

## Changes needed for schema generation

- Describe existing JWT and service-token authentication for OpenAPI.
- Add schema-only payment response serializers and annotations, and enable
  drf-spectacular for payment-sim. No payment service logic is changed.
- Resolve the observed existing `APIView -> DenyAll -> APIView` import cycle:
  APIView is imported only under TYPE_CHECKING; postponed annotations retain
  the type information. DenyAll still denies access and passenger checks are
  unchanged. This was necessary to load the schema generator.
- Add optional contract validator groups, three lockfiles, generated contracts,
  examples, verification tools, local Python ignore rules and a CI contract job.
- Existing touched text files are normalized to LF; this can make their raw
  diffs larger. Review with whitespace ignored to isolate semantic changes.

No purchase/payment/validation business operation, model, migration, feature
endpoint, deployment, retention policy or unresolved A-series decision was
implemented or changed. MET-169/MET-87 documents and other tasks are untouched.
The existing CI trigger policy and other job definitions are preserved.

## Review still required

The team must review the contract shapes, versioning policy, optional JSON Schema
dialect support in AsyncAPI tooling, existing source gaps and code changes above.
The event receiver is deliberately only a contract probe. Future independent
application consumers require their own compatibility evidence; do not label
this as a successful notification-service integration test.

MET-87 acceptance, review/approval, commit/PR links and GitHub check results are
Pending. A local pass or first contract version does not resolve those gates.
No review, passing pipeline, external approval or release is fabricated.

Codex prepared the code/contracts/docs and performed the stated local checks.
The student executed the interactive commands and retains control of commits,
push and PR creation. Human edits and review effort are recorded when supplied.
