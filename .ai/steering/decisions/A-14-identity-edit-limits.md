# ADR A-14: Limits on Editing Identity Data vs. Contact Details

- **Status:** Proposed for Team Approval (pending PR review)
- **Date:** 2026-11-19
- **Author:** João Pedro Xia (`jpx`, Core Backend Lead)
- **Related Requirements:** FR-020, FR-022, FR-023, FR-102, FR-103, FR-105, NFR-056, NFR-081
- **Related Design / Decisions:** DES-01 (`MET-169`), NFR-005 (`MET-87`), A-06 (`MET-159`), A-07 (`MET-160`), A-09 (`MET-162`), E2E-02 (`MET-179`)
- **Linear Issue:** [MET-167](https://linear.app/metroisjustabus-ase/issue/MET-167/a-14-confirm-limits-on-editing-identity-data)

---

## 1. Context and Problem Statement

In Requirements Specification v0.2 (section 5, page 17), assumption **A-14** leaves open the exact boundary between immutable passenger identity data and editable profile/contact details:

> *"Whether passengers may edit identity data when personal tickets depend on it."*
> Working assumption: *"Passengers edit contact data and notification preferences only; changes to identity data are out of scope for now (FR-022)."*

Before implementing profile consultation and contact updates (`FR-022` / `MET-21`) or account deletion workflows (`FR-023` / `MET-22`), the team must define:
1. Exactly which attributes are treated as **protected identity data** versus **editable contact data**.
2. How self-service profile updates behave when a passenger attempts to modify protected identity attributes.
3. How already-issued personal tickets, purchase records, and notification delivery interact with profile edits.

### Alignment with the Original Project Brief (v1.0, 29 September 2026)

Checking pages 7–9 (*Technical Description* and *Application and Architecture*):
- **Explicitly required by the brief:** Passenger accounts, account-associated tickets, passenger consultation of accounts/tickets, passenger notification subscriptions/preferences, and preservation/auditing of issued operational and ticketing history.
- **Not specified by the brief (team-derived choices):** Which exact fields constitute immutable identity vs. mutable contact details (`User.email` and `AccountProfile.full_name` vs. `AccountProfile.contact_email` and `AccountProfile.phone`), whether identity attributes are read-only in v1 or gated by a verification workflow, and the HTTP validation policy when clients attempt to edit protected fields.

---

## 2. Decision

The team confirms and adopts the **A-14** working assumption with the following concrete field-level boundary for MVP (v1):

### 2.1 Protected Identity Fields (Immutable via Self-Service Profile Edits)

The following attributes represent account identity and entitlement bindings and **cannot be modified** through passenger self-service profile endpoints (`FR-022`):

| Entity & Field | Role in the System | Policy in v1 |
|---|---|---|
| `User.id` | Authoritative UUID subject (`sub` JWT claim, `passenger_id` reference in `ticketing-service` and `notification-service`) | Immutable system-generated UUID |
| `User.email` | Login credential identifier | Read-only in profile endpoints; changes require a future verified identity-change workflow (out of scope for v1) |
| `AccountProfile.full_name` | Passenger name bound to account identity and personal-ticket holder attribution | Read-only after registration (`FR-020`) in v1 |
| `RoleAssignment` (`role`, `active`), `User.status` | Authorization role (`passenger` / `staff`) and account lifecycle state | Server-managed only (`A-07`); never editable via profile API |

### 2.2 Mutable Contact & Notification Data (Editable by the Owning Passenger)

The following attributes exist strictly for passenger communication and notification delivery and **are editable** by the authenticated passenger (`IsPassenger` + owner isolation under `FR-102`):

| Entity & Field | Owner Service | Purpose & Constraints |
|---|---|---|
| `AccountProfile.contact_email` | `core-backend` | Delivery email used for `EMAIL` notifications (`A-06`). Separating `contact_email` from login `User.email` allows passengers to change where alerts are delivered without altering login identity or ticket ownership. Must remain a valid email format. |
| `AccountProfile.phone` | `core-backend` | Optional contact phone number (`max_length=32`, may be blank). |
| Notification preferences & subscriptions (`FR-060`–`FR-062`) | `notification-service` | Channel enablement (`IN_APP`, `EMAIL`), change-type filters, and subscribed lines/stops/trips, managed directly via `notification-service` APIs. |

### 2.3 Protection of Personal Tickets & Historical Records

1. **Ticket & purchase immutability:** Issued tickets and purchases in `ticketing-service` bind to the immutable `User.id` (`passenger_id`) and snapshot purchased terms (`terms_snapshot`). Editing `contact_email` or `phone` in `core-backend` **never alters** issued tickets, purchase history, or validation records (`FR-103`, `FR-105`, `NFR-081`).
2. **Server-side enforcement on `FR-022` endpoints:**
   - Profile retrieval (`GET`) exposes both read-only identity context (`id`, `email`, `fullName`) and editable contact details (`contactEmail`, `phone`).
   - Profile update (`PATCH` / `PUT`) accepts only `contactEmail` and `phone`. Attempts to submit protected identity fields (`id`, `email`, `fullName`, `role`, `status`) must be rejected explicitly (`400 VALIDATION_ERROR`) — never silently applied.
3. **Contact-data minimization (`NFR-056`):**
   - Only the authenticated owning passenger may view or edit their `AccountProfile` (`FR-102`).
   - `notification-service` consumes minimized contact delivery details only as required to dispatch external sandboxed email notifications and never mutates core identity state.
4. **Relationship to account deletion (`FR-023` / `A-09`):**
   - Account deletion/anonymization semantics remain separately governed by **`A-09` (`MET-162`, history retention)** so deletion never cascades destructively over issued tickets or operational audit history (`DES-01`).

---

## 3. Impact Assessment

- **Requirements & Assumptions:** Preserves the working assumption in `.ai/sdd/specs/domain-data-ownership/assumptions.md` (`A-14`) and `FR-022` scope without changing any v0.2 requirement priority.
- **Data Model (`DES-01` / `MET-169`):** Confirmed without schema changes — `AccountProfile` already separates `full_name` (identity) from `contact_email` and `phone` (mutable contact details), while `User` owns `id` and login `email`.
- **Components Affected:**
  - `apps/core-backend` (`MET-21` / `FR-022`): implement owner-scoped profile view (`GET`) and contact-only update (`PATCH`), enforcing immutable identity validation and explicit tests verifying identity fields and ticket attribution cannot be altered.
  - `apps/notification-service`: continues retrieving minimized recipient contact data via an explicit core contract without touching identity fields.
  - `apps/web`: renders `email` and `fullName` as read-only in profile settings while letting passengers edit `contactEmail`, `phone`, and notification preferences.
- **Verification Criteria (`FR-022`, `E2E-02`):** Tests must demonstrate that:
  1. An authenticated passenger can view their profile and update `contactEmail` and `phone`.
  2. Attempts to modify `fullName`, login `email`, `id`, or `role` are rejected with `400 VALIDATION_ERROR` and leave stored identity data unchanged.
  3. Existing tickets owned by `User.id` remain valid and unaffected after contact updates.

---

## 4. Consequences

### Positive
- Eliminates ambiguity before implementing `MET-21` (`FR-022`) profile endpoints and UI views.
- Allows passengers to change their notification contact address (`contact_email`) freely without weakening login credentials or personal-ticket identity binding.
- Reuses the exact `User` / `AccountProfile` schema split already established in `DES-01` and `apps/core-backend/accounts/models.py`.

### Negative / Trade-offs
- Passengers cannot self-update their login `User.email` or registered `full_name` in v1 (typo corrections require out-of-band/admin support until a verified email/identity-change workflow is prioritized beyond MVP).
- Exposes both login `email` (immutable) and `contactEmail` (mutable) in the profile payload, which UI labels should clearly distinguish so passengers understand login email stays fixed while notification contact email can change.
