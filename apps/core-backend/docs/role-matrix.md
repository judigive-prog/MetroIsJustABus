# Role-to-Operation Matrix (`FR-100`, `FR-101`, `NFR-050`)

This matrix defines the access rules enforced at the server boundary in `apps/core-backend` and aligns with the v1 human role model documented in `A-07` (`MET-160`).

## 1. Roles

| Role | Identity & Authentication | Scope |
|---|---|---|
| `visitor` | Unauthenticated caller (`request.user is None`, no bearer token) | Public endpoints annotated with `AllowAny` only |
| `passenger` | Authenticated human user with `User.status == ACTIVE`, active `AuthSession`, and active `RoleAssignment(role="passenger")` | Public endpoints, authenticated session endpoints, and passenger-scoped endpoints (`IsPassenger`) |
| `staff` | Authenticated human user provisioned server-side with `User.status == ACTIVE`, active `AuthSession`, and active `RoleAssignment(role="staff")` | Public endpoints, authenticated session endpoints, and operational staff endpoints (`IsStaff`) |

### Non-Human & Unrecognized Actors
- Service-to-service callers and hardware devices (such as ticket validators) never use `passenger` or `staff` human roles (`NFR-053`).
- Any JWT carrying an unrecognized `role` claim, a role mismatching its `AuthSession`, or a revoked `RoleAssignment` is rejected at `JWTAuthentication` with `401 NOT_AUTHENTICATED`.

## 2. Server-Boundary Enforcement Rules

- **Fail-closed default (`DenyAll`):** `REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"]` is set to `["common.permissions.DenyAll"]`. Any view that omits `permission_classes` denies all callers (`401 NOT_AUTHENTICATED` for `visitor`, `403 PERMISSION_DENIED` for authenticated callers).
- **No self-escalation on registration:** `POST /api/core/v1/auth/register` always creates `RoleAssignment(role="passenger")` and ignores any client-supplied `role` or `status`.
- **Status semantics:**
  - `401 NOT_AUTHENTICATED` — missing, malformed, expired, revoked, wrong-role-claim, or disabled-account credentials.
  - `403 PERMISSION_DENIED` — valid authenticated session holding a role not permitted on the endpoint (for example, `passenger` calling an `IsStaff` endpoint, or `staff` calling an `IsPassenger` endpoint).

## 3. Operation Matrix

### 3.1 Implemented Endpoints (`core-backend`)

| Operation / Route | Permission Class | `visitor` | `passenger` | `staff` |
|---|---|---|---|---|
| `GET /health/live`, `GET /health/ready` | Public Django probe (`AllowAny` equivalent) | Allow (`200` / `503`) | Allow (`200` / `503`) | Allow (`200` / `503`) |
| `GET /api/core/v1/schema` | `AllowAny` (`SERVE_PERMISSIONS`) | Allow (`200`) | Allow (`200`) | Allow (`200`) |
| `POST /api/core/v1/auth/register` | `AllowAny` (`passenger` role forced) | Allow (`201`) | Allow (`201`) | Allow (`201`) |
| `POST /api/core/v1/auth/login` | `AllowAny` | Allow (`200` / `401`) | Allow (`200` / `401`) | Allow (`200` / `401`) |
| `GET /api/core/v1/auth/jwks` | `AllowAny` | Allow (`200`) | Allow (`200`) | Allow (`200`) |
| `GET /api/core/v1/auth/session` | `IsAuthenticatedRole` | `401 NOT_AUTHENTICATED` | Allow (`200`) | Allow (`200`) |
| `POST /api/core/v1/auth/logout` | `IsAuthenticatedRole` | `401 NOT_AUTHENTICATED` | Allow (`204`) | Allow (`204`) |

### 3.2 Implemented Downstream Service Operations (`ticketing-service`, `notification-service`)

All downstream services decode RS256 JWTs issued by `core-backend` (`sub`, `role`, `exp`, `iss`) and enforce the same `DenyAll` / `IsPassenger` / `IsStaff` permission model:

| Service & Operations | Permission Class | `visitor` | `passenger` | `staff` |
|---|---|---|---|---|
| `ticketing`: `GET /api/ticketing/v1/ticket-types` | `AllowAny` | Allow (`200`) | Allow (`200`) | Allow (`200`) |
| `ticketing`: `POST /api/ticketing/v1/purchases`, `GET /api/ticketing/v1/purchases/{id}` | `IsPassenger` | `401` | Allow (owner-isolated) | `403 PERMISSION_DENIED` |
| `notifications`: `GET/POST /api/notifications/v1/subscriptions`, `PATCH/DELETE /subscriptions/{id}` | `IsPassenger` | `401` | Allow (owner-isolated) | `403 PERMISSION_DENIED` |
| `notifications`: `GET/PUT /api/notifications/v1/preferences`, `PUT/PATCH /preferences/{channel}` | `IsPassenger` | `401` | Allow (owner-isolated) | `403 PERMISSION_DENIED` |
| `notifications`: `GET /api/notifications/v1/inbox`, `POST/PATCH /inbox/{id}/read`, `POST /inbox/read-all` | `IsPassenger` | `401` | Allow (owner-isolated) | `403 PERMISSION_DENIED` |

### 3.3 Planned Feature Boundaries in `core-backend`

Upcoming feature issues build directly on these permission classes without inventing extra v1 roles:
- **Public network, schedules, trips, disruptions (`FR-001`–`FR-014`, `FR-024`):** `AllowAny` (accessible to `visitor`, `passenger`, `staff`).
- **Passenger profile & account deletion (`FR-022`, `FR-023`, `FR-102`):** `IsPassenger` (owner-isolated by `request.user.id`).
- **Operational staff maintenance & disruption simulation (`FR-070`–`FR-076`, `FR-090`–`FR-096`, `FR-101`):** `IsStaff` under `/api/core/v1/staff/...` (`visitor` gets `401`, `passenger` gets `403`).
