# Principles — MetroIsJustABus

1. A ticket journey is never spent twice. Validation locks the ticket row, decides, records the validation and writes its event in one transaction. (FR-046, NFR-030)
2. Every retry-safe operation is idempotent through a database constraint, not only application code: purchase, validation, occupancy update, notification. A repeated request or event has one effect. (FR-033, FR-045, FR-055, FR-066, NFR-013)
3. A purchase never issues a ticket without a confirmed payment, and a confirmed payment always ends in exactly one ticket. A step that fails midway is reconciled, never left half-done. (FR-033, NFR-015)
4. Every entity has one owning component. No component reads or writes another component's database. Other services refer to it by UUID only. (NFR-004, NFR-032)
5. Purchase, validation and consultation never wait on notification or occupancy. Effects across components are asynchronous, and a component outage never blocks them or loses events. (NFR-020, NFR-021)
6. The server checks permissions before business logic, always. The client is a hint, not an authority. A passenger only ever reaches their own tickets, subscriptions and notifications. (FR-100 to FR-102, NFR-050)
7. Issued tickets and history are never rewritten. Changing a ticket type does not change tickets already issued, history tables are append-only, and business data is deactivated, not deleted. (FR-081, FR-103)
8. A change to network, schedule or disruption is never silent: it is audited, and it emits an event so affected passengers are notified. (FR-069, FR-075, FR-095, NFR-057)
9. Never show silently wrong data. Stale or missing information is labelled as such. Occupancy is always an estimate, never presented as real-time or as proof of over-capacity. (FR-056, NFR-024)
10. Nothing is correct because an AI produced it. Every change passes tests, static analysis and human review before merge, and every change traces to a requirement ID. (NFR-087, NFR-112)
11. If a requirement depends on an open assumption (A-03 occupancy attribution, A-06 channels, NFR targets), stop and ask. Do not decide it in code.
12. If you are uncertain whether something is in scope, it is not.
