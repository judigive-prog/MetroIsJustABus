# Review Log — Notification Service

## 2026-11-10 — Service Kickoff & Decision A-06
- **Present:** Alexandre Faustino (M4 - Backend Notifications & Occupancy)
- **Decisions Approved:**
  - **A-06 (Notification Channels):** Approved in-app inbox (persistent, deduplicated) and email (sandboxed via Mailpit SMTP). See `.ai/steering/decisions/A-06-notification-channels.md`.
  - **Linear Tasks:** All 13 notification tasks assigned to Alexandre Faustino on `MetroIsJustABus-ASE`.
  - **Scaffolding:** `apps/notification-service` initialized with Django 5.2 LTS, DRF, JWT auth with JWKS cache, structured logging, health probes, and Dockerfile.
