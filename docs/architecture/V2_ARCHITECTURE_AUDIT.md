# VEXUS v2 Architecture Audit

Date: 2026-09-08

## Baseline Verification

- Backend: `185 passed` with `backend/.venv/Scripts/python.exe -m pytest -q`.
- Frontend: `npm run build` passes in `frontend/`.
- Authentication: seeded admin login succeeds using the configured username and password; email login is supported.
- Database: development uses SQLite through `DATABASE_URL`; relative SQLite paths depend on the process working directory.
- Discovery: authorized scan scope is enforced before collection; collectors are injected through a FastAPI dependency for testability.

## Current Architecture

### Backend

FastAPI routes are organized by domain under `backend/app`. The current domains are:

- `auth`, `users`, and `audit`: authentication, RBAC, and audit records.
- `assets`: asset storage, filtering, metadata updates, and append-only history.
- `discovery`: scan jobs, authorization checks, collector abstraction, and asset upserts.
- `monitoring`, `events`, `detection`, and `alerts`: operational observations through alert generation.
- `topology`: asset relationships and topology queries.
- `incidents`, `risk`, and `ai`: investigation, explainable risk, and grounded explanations.
- `sense`: behavioral baselines and anomaly events.
- `health`: application health reporting.

SQLAlchemy models and repositories own persistence. Services contain domain behavior. Routers enforce authentication and role checks before calling services.

### Frontend

The React/TypeScript application uses route-level pages, shared components, hooks, and service modules under `frontend/src`. API calls are centralized in service files and authenticated through the existing auth hook. The production bundle currently compiles successfully.

## Findings

### Working foundations

- Authentication, JWT validation, RBAC, and audit logging are covered by tests.
- Asset CRUD/read paths, asset history, status fields, search/filter parameters, and risk metadata exist.
- Discovery supports authorized ranges, collector injection, scan history, new assets, changed assets, and stale asset handling.
- Event normalization, detection, alerts, incidents, risk, AI, and Sense are implemented beyond the original V2 starting point.
- Full backend test collection is constrained to `tests/` so binary/log artifacts do not become test modules.

### V2 gaps

- Correlation now exposes read-only incident candidates by grouping active,
  unsuppressed alerts on the same asset within a configurable time window.
- No threat-intelligence adapter or vulnerability data model is present.
- No SIEM/syslog ingestion boundary is present.
- No identity integration boundary is present.
- No durable background worker/scheduler exists for recurring discovery, monitoring, detection, or baseline calculation.
- Frontend automated tests are not currently configured beyond TypeScript/build validation.
- SQLite path selection remains process-directory dependent for local development.

## First V2 Milestone

### Asset Intelligence and Authorized Network Discovery hardening

The next implementation slice should make asset identity and discovery results reliable enough for later correlation and threat intelligence:

1. Define one canonical asset identity/upsert policy for MAC, IP, and hostname observations.
2. Preserve every identity transition in `AssetHistory` with a source and timestamp.
3. Expose deterministic asset search/filter behavior for the frontend.
4. Add service/API tests for repeated discovery, identity changes, and stale assets.
5. Document the local database working-directory requirement or normalize development startup around one path.

### Acceptance criteria

- Repeated discovery of the same host does not create duplicate assets.
- MAC changes, IP changes, hostname changes, and stale transitions are auditable.
- Authorized discovery cannot write assets from an unauthorized target range.
- Asset list filters and history return stable, documented results.
- Backend and frontend verification remain green.

The asset-intelligence milestone and the first Correlate slice are complete.
Correlate candidates are projections only; analysts still create incidents
through the existing Trace workflow. V2 should proceed to threat intelligence
and ingestion boundaries, with worker execution added before continuous
operation is claimed.
