# ADR A-07: Operational Staff Role and Sub-Role Model

- **Status:** Proposed for Team Approval (pending PR review)
- **Date:** 2026-11-17
- **Author:** João Pedro Xia (`jpx`, Core Backend Lead)
- **Related Requirements:** FR-070–FR-076, FR-080–FR-084, FR-090–FR-096, FR-100, FR-101, FR-102, NFR-050, NFR-053
- **Related Design / Tests:** DES-01 (`MET-169`), NFR-005 (`MET-87`), NFR-006 (`MET-88`), E2E-07 (`MET-184`)
- **Linear Issue:** [MET-160](https://linear.app/metroisjustabus-ase/issue/MET-160/a-07-confirm-the-staff-role-and-possible-sub-roles)

---

## 1. Context and Problem Statement

In Requirements Specification v0.2 (section 5, page 16), assumption **A-07** captures an open design question:

> *"Who counts as 'operational staff' and whether there are sub-roles."*
> Working assumption: *"One staff role initially, with room to split it (for example dispatcher, ticket manager)."*

Before implementing `apps/core-backend/` authentication, role issuance and staff endpoints (`FR-020`, `FR-021`, `FR-070`–`FR-076`, `FR-090`–`FR-096`, `FR-100`, `FR-101`, `NFR-050`), the team must confirm:
1. Whether MVP uses a single operational staff role or fine-grained staff sub-roles.
2. How `visitor`, `passenger`, `staff`, and non-human service/device identities are represented and separated.
3. Whether one identity can hold multiple roles and how staff accounts are provisioned.
4. How the JWT claims issued by `core-backend` stay compatible with the existing downstream services (`ticketing-service` and `notification-service`).

### Alignment with the Original Project Brief (v1.0, 29 September 2026)

Checking pages 7–8 (*Technical Description: passengers, accounts and operational staff*):
- **Explicitly required by the brief:** Operational staff and passengers are distinct actors; staff maintenance functions (network, schedules, ticket types, disruptions, monitoring) must be restricted to operational staff, and passengers must have account-associated access.
- **Not specified by the brief (team-derived choices):** Whether staff permissions are split into sub-roles (`dispatcher`, `ticket_manager`, etc.), whether `User` and `RoleAssignment` share one table or separate tables, whether a user can hold multiple roles, how staff accounts are provisioned, and the exact JWT claim format.

---

## 2. Decision

The team adopts the A-07 working assumption with the following concrete model for MVP (v1):

### 2.1 User Roles in v1

The system enforces three human access levels at the server boundary (`FR-100`, `NFR-050`):

1. **`visitor` (unauthenticated caller):**
   - No `User` record and no JWT.
   - Permitted only on explicitly annotated `AllowAny` public read endpoints (network/schedule consultation, active ticket types catalogue, health probes and OpenAPI schema).
2. **`passenger` (claim `role = "passenger"`):**
   - Self-registered account via the public registration endpoint (`FR-020`).
   - Permitted on passenger-scoped resources (purchases, tickets, validation history, subscriptions, preferences, inbox), with per-owner isolation (`FR-102`).
3. **`staff` (claim `role = "staff"`):**
   - **Single operational staff role for v1**, authorized across all `/api/{service}/v1/staff/...` endpoints (`FR-101`), covering network/schedule maintenance (`FR-070`–`FR-076`), ticket-type/usage staff views (`FR-080`–`FR-084`), disruption management (`FR-090`–`FR-096`) and staff occupancy views (`FR-052`).
   - Fine-grained sub-roles (e.g., `dispatcher`, `ticket_manager`) are **explicitly deferred to v2+** (consistent with `.ai/steering/product.md`).

### 2.2 Non-Human Actors (Excluded from Staff Role)

Validators, disruption/payment simulators and service-to-service calls are **not** `staff` or `passenger` user roles (`NFR-053`, `.ai/steering/conventions.md` §Calls):
- Validators and inter-component calls authenticate with dedicated service/device credentials (separate token/role such as `service` or `validator`, never `passenger` or `staff`).
- Note: The disruption simulator (`FR-096`) simulates staff stimuli through the staff API boundary (`A-02`), using a provisioned test staff credential or dedicated test harness configuration — never by bypassing `IsStaff`.

### 2.3 Identity Storage, Multi-Role Extensibility, and Provisioning (`DES-01`)

1. **Unified identity + `RoleAssignment` (`core-backend`):**
   - All human accounts share the `User` entity in `core-backend` (`NFR-032`), paired with `RoleAssignment` (`user_id`, `role`, active/revoked lifecycle metadata) as modelled in `.ai/sdd/specs/domain-data-ownership/design.md`.
   - Keeping roles in `RoleAssignment` rather than hardcoded boolean columns or separate `Passenger`/`Staff` credential tables allows adding sub-roles later without migrating user credentials.
2. **Primary role per account in v1 & JWT compatibility:**
   - Downstream services (`apps/ticketing-service/common/auth.py` and `apps/notification-service/common/auth.py`) already decode RS256 JWTs reading `sub` (user UUID) and a scalar string claim `role` (`"passenger"` or `"staff"`), and enforce `DenyAll` by default plus `IsPassenger` / `IsStaff` (`apps/notification-service/common/permissions.py`).
   - In v1, `core-backend` issues RS256 JWTs carrying `"sub": "<user_uuid>"` and `"role": "passenger" | "staff"` (plus `"exp"` and `"iss"`).
   - If future sub-roles are introduced in v2+, they will be added in a backward-compatible way (e.g. an additive `"scopes"` or `"subRoles"` claim alongside `"role": "staff"`) so existing `v1` services do not break.
   - In v1, each account holds one active role at login time (separate accounts for passenger vs staff testing avoids privilege ambiguity).
3. **Staff Provisioning:**
   - Public self-registration (`FR-020`) **always** assigns `"passenger"` and ignores or rejects any client-supplied role attribute (`.ai/steering/principles.md` #6).
   - Staff accounts are provisioned **only** via server-side administrative tooling (`manage.py` management commands / deterministic test/dev seed fixtures in `DATA-01`) — never via a public HTTP endpoint.

### 2.4 Server-Side Enforcement Boundary

- Every DRF view declares explicit permission classes; the global default remains `DenyAll`.
- Staff endpoints live exclusively under `/api/{service}/v1/staff/{resource}` and require `IsStaff` (`.ai/steering/conventions.md` §API).
- Passenger endpoints require `IsPassenger` (`staff` callers receive `403 Forbidden`, unauthenticated callers receive `401 Unauthorized`, as already verified in `apps/ticketing-service/purchases/tests/test_purchase_api.py`).
- All staff mutations record an immutable `StaffAudit` entry with `actor_id` (`sub`) in the same database transaction (`NFR-057`, `FR-095`).

---

## 3. Impact Assessment

- **Requirements & Assumptions:** Confirms the working assumption in `.ai/sdd/specs/domain-data-ownership/assumptions.md` (`A-07`) without altering v0.2 priorities or scope.
- **Components Affected:**
  - `apps/core-backend`: `User`, `RoleAssignment`, registration (`passenger` only), login/token issuance (`sub`, `role`), `IsStaff`/`IsPassenger` permissions, and `manage.py` staff seed/provisioning command.
  - `apps/ticketing-service` & `apps/notification-service`: Existing `JWTAuthentication` (`claims["sub"]`, `claims["role"]`) and `IsPassenger` / `IsStaff` classes already match this decision with zero breaking changes.
  - `apps/web`: UI hides staff routes/controls for non-staff, while server permissions remain authoritative (`FR-101`).
- **Verification & Acceptance (`FR-100`, `FR-101`, `E2E-07`):** Tests must cover visitor (`401` on protected endpoints), passenger (`403` on staff endpoints), and staff (`403` on passenger-only endpoints such as purchase creation, `200`/`201` on staff endpoints), plus verifying public sign-up cannot self-elevate to `staff`.

---

## 4. Consequences

### Positive
- Eliminates ambiguity before `core-backend` auth implementation (`MET-114`, `MET-19`, `MET-20`, `MET-77`).
- Matches the exact JWT claims and permission classes already implemented in `ticketing-service` and `notification-service`.
- Keeps a clean migration path to staff sub-roles in v2+ via `RoleAssignment` and additive JWT claims.
- Prevents privilege-escalation risk during registration by prohibiting client-chosen roles and public staff sign-up.

### Negative / Trade-offs
- All authenticated operational staff share full staff privileges in v1 (acceptable for MVP scope; documented in `product.md` and `DES-01`).
- Staff account creation requires CLI/seed access in v1 until a dedicated staff-administration workflow is prioritized.
