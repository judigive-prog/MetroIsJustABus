# .ai/steering/principles.md

# Principles — MetroIsJustABus

1. A ticket journey is never spent twice. Validation locks the ticket row, decides, records the validation and writes its event in one transaction. (FR-046, NFR-030)
2. Every retry-safe operation is idempotent through a database constraint, not only application code: purchase, validation, occupancy update, notification. A repeated request or event has one effect. (FR-033, FR-045, FR-055, FR-066, NFR-013)
3. A purchase never issues a ticket without a confirmed payment, and a confirmed payment always ends in exactly one ticket. A step that fails midway is reconciled, never left half-done. (FR-033, NFR-015)
4. Every entity has one owning component. No component reads or writes another component's database. Other services refer to it by UUID only. (NFR-004, NFR-032)
5. Events are published only through the outbox, in the same transaction as the state change. Consumers check the inbox first and tolerate duplicate, delayed and out-of-order delivery. (NFR-014, NFR-015)
6. Purchase, validation and consultation never wait on notification or occupancy. Effects across components are asynchronous, and a component outage never blocks them or loses events. (NFR-020, NFR-021)
7. Every call between components has a timeout and a defined behaviour on failure. Nothing waits without a limit. (NFR-012)
8. The server checks permissions before business logic, always. The client is a hint, not an authority. A passenger only ever reaches their own tickets, subscriptions and notifications. (FR-100 to FR-102, NFR-050)
9. Issued tickets and history are never rewritten. Changing a ticket type does not change tickets already issued, history tables are append-only, and business data is deactivated, not deleted. (FR-081, FR-103)
10. A change to network, schedule or disruption is never silent: it is audited, and it emits an event so affected passengers are notified. (FR-069, FR-075, FR-095, NFR-057)
11. Never show silently wrong data. Stale or missing information is labelled as such. Occupancy is always an estimate, never presented as real-time or as proof of over-capacity. (FR-056, NFR-024)
12. The contract is the interface. An API or event change updates the committed contract in the same pull request, or it does not merge. (NFR-006)
13. Time-dependent rules read the injected clock, and storage is UTC. (NFR-033)
14. Secrets never appear in source control, images or logs. Personal data is never logged. (NFR-054, NFR-056)
15. Nothing is correct because an AI produced it. Every change passes tests, static analysis and human review before merge, and every change traces to a requirement ID. (NFR-087, NFR-112)
16. Environments change only through version-controlled configuration and the pipeline. The image that passed dev is the image that goes to prod. (NFR-094, NFR-097)
17. If a requirement depends on an open assumption (A-03 occupancy attribution, A-06 channels, NFR targets), stop and ask. Do not decide it in code.
18. If you are uncertain whether something is in scope, it is not.
