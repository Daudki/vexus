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
- No identity integration boundary is present.
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
through the existing Trace workflow.

## Update: 2026-09-12 — Background Scheduler

The worker-execution gap noted above is closed. `app/core/scheduler.py`
adds an in-process asyncio scheduler (no new infra dependency) that
reuses the existing manual-trigger service methods directly —
`MonitoringService.poll_all()`, `DetectionEngine.run()`,
`DiscoveryService.run_scan()`, and a new `SenseService.evaluate_all_assets()`
— so there remains exactly one implementation of each behavior, not a
scheduler-specific copy.

- Off by default (`Settings.SCHEDULER_ENABLED=false`); each job type runs
  on its own independent loop and interval so one slow/failing job
  cannot block the others.
- Scheduled discovery only runs if `AUTHORIZED_SCAN_RANGES` is actually
  configured, per this document's own discovery-authorization rule.
- `DiscoveryService.run_scan()`'s `initiated_by` parameter is now
  optional, matching the pattern already used by `MonitoringService` and
  `DetectionEngine`, so a scheduled run has no user to attribute the
  action to.
- `HealthService` (`GET /health/`) now reports live status per worker
  (`monitoring`, `discovery`, `detection`, `sense`) — `unknown` if a
  cycle has never run, `ok`/`degraded` from the worker's own heartbeat,
  automatically downgraded to `degraded` if the last success is more
  than 15 minutes old even if the recorded status was `ok`. Previously
  this endpoint only checked database connectivity, despite the
  `WorkerHeartbeat` model's own docstring already claiming it did.
- Verified against a running server, not just pytest: with the
  scheduler enabled on a short interval, `GET /health/` transitioned
  monitoring/detection/sense from `unknown` to `ok` with no manual
  trigger, and the dashboard's "Monitoring has not completed a poll
  cycle yet" warning (`GET /api/v1/monitoring/overview`) cleared on its
  own once the first cycle completed.
- 204/204 backend tests pass (up from 185 at the last audit date).

V2 should proceed to threat intelligence and ingestion boundaries next.

## Update: 2026-09-12 — External Event Ingestion Boundary

The syslog/threat-intel ingestion gap is closed for the generic case
(a real threat-intel *adapter* — parsing a specific feed format — is
still not built; this is the boundary any such adapter would call).

- `app/events/router.py` (`POST /api/v1/events/ingest`) accepts a batch
  of externally-sourced events restricted to `event_source` ∈
  `{syslog, threat_intel, manual}` — `discovery`/`monitoring` are
  rejected (422) to prevent an external caller from impersonating a
  first-party subsystem, and `simulation` is rejected for the same
  reason Simulation Mode's own docstring reserves that flag to itself.
- Assets are resolved by `ip_address` via the existing
  `AssetRepository.get_by_ip()` (no second lookup implementation); an
  unmatched IP does not fail the request — the event is stored with
  `asset_id=null` and the raw IP preserved in `event_metadata`, since
  discarding unmatched telemetry silently would be a worse outcome than
  storing it unresolved.
- `is_synthetic` and `processed_by_detection` are never settable by the
  caller — every ingested event is real, unprocessed data by
  construction, so it flows into the exact same `DetectionEngine.run()`
  pass as discovery- and monitoring-sourced events. Verified directly:
  an ingested `AVAILABILITY_ANOMALY` event produces an alert through
  the unmodified detection pipeline.
- Batches are all-or-nothing: one invalid event (bad `asset_id`,
  oversized evidence/metadata) rolls back the whole request rather than
  partially ingesting.
- No new auth primitive was introduced — ingestion uses the same
  bearer-JWT RBAC as every other endpoint (Admin/Security
  Analyst/Network Administrator), on the reasoning that a syslog
  forwarder or threat-intel feed should authenticate as a dedicated
  service account rather than needing a second auth mechanism built
  just for this. A real API-key model remains a reasonable future
  enhancement if that assumption doesn't hold up in practice.
- 218/218 backend tests pass (up from 204 after the scheduler work).

Still open: an actual threat-intel feed adapter (this boundary accepts
`threat_intel`-sourced events but nothing yet fetches or parses a real
feed), a vulnerability data model, and identity integration.

## Update: 2026-09-13 — Foundation Audit

Before adding further features, the load-bearing pieces were checked
directly rather than assumed from passing tests (the test suite
bootstraps schema via `Base.metadata.create_all()`, which can mask
migration-specific bugs — see the first finding below).

**Fixed:**
- **`behavioral_baselines` had no migration at all.** `alembic upgrade
  head` against a genuinely fresh database never created this table —
  every Sense operation (`compute_baseline`, `evaluate_asset`,
  `evaluate_all_assets`, and the scheduler's sense loop) would fail
  with "relation does not exist" in any real deployment. Added
  `alembic/versions/3fcbb6484f90_phase_9_sense_behavioral_baselines.py`;
  verified upgrade and downgrade both apply cleanly from scratch, and
  confirmed zero drift between the full migrated schema and every
  SQLAlchemy model (table-by-table, column-by-column, not spot-checked).
- **`Settings.SECRET_KEY` had a hardcoded, working default**
  (`"dev-secret-key-change-me"`) — since this is a public repo, that
  exact string was public too. A deployment that forgot to override it
  wouldn't fail or warn; it would run normally, signing real JWTs with
  a key anyone could read from source. Removed the default entirely
  (now a required field — a ValidationError at startup, not a silent
  vulnerability) and confirmed the full test suite still passes with
  zero `.env` file present, proving it no longer has any implicit
  dependency on a real secret existing on disk.
- **`AUTHORIZED_SCAN_RANGES` had no ceiling on how broad an entry could
  be.** Nothing stopped an operator from authorizing `0.0.0.0/0`
  (the entire internet) or anything comparably broad, which would
  silently defeat the entire point of an explicit, narrow
  authorization allowlist. `app/discovery/scope.py` now rejects (with
  a logged warning, not a crash) any authorized-range entry broader
  than a /8 — chosen specifically so the common legitimate case
  (`10.0.0.0/8`, the entire RFC1918 10.x block) still works.

**Audited, found already correct — no change needed:**
- RBAC coverage across every router endpoint, checked individually,
  not sampled: every data-mutating or data-reading endpoint requires
  authentication; the only unauthenticated ones (`/auth/login`,
  `/auth/refresh`, the three `/health/*` probes) are correctly
  unauthenticated by design.
- Transaction/commit consistency across every repository and service
  file: no method flushes without an eventual commit in the same file
  (this exact bug class was found and fixed earlier in `get_db()` and
  the users repository — this confirms it wasn't a wider pattern).
- CORS configuration: explicit origin allowlist, not wildcarded;
  correctly paired with `allow_credentials=True` (browsers reject that
  combination with a wildcard origin regardless).
- No other settings field carries a hardcoded secret/key/password-style
  default; API keys are all `Optional[str] = None` and degrade to a
  disabled/null provider rather than a fake working credential.

218 -> 222 backend tests (new coverage for the scan-range ceiling).
Limitation: this audit was done against SQLite; a real Postgres
instance was not available to verify the new migration's enum-reuse
behavior (`create_type=False`) end-to-end — the pattern used is the
standard, documented Alembic approach for this exact situation, but it
has not been executed against live Postgres in this environment.

## Update: 2026-09-13 — Threat Intelligence (NVD CVE Feed)

The remaining named V2 gap ("an actual threat-intel feed adapter... a
vulnerability data model") is closed. `app/threat_intel/` adds an NVD
2.0 CVE API adapter: `POST /api/v1/threat-intel/sync/cve/{id}` fetches
and normalizes a single CVE record into a new `vulnerabilities` table,
and emits a `NetworkEvent` (`event_source=threat_intel`) through the
same event contract the ingestion boundary already established — no
second event-writing path. Off by default (`NVD_ENABLED=false`).

This was contributed externally and merged in, including fixing a real
migration-chain fork (it branched from the same parent as the
just-added `behavioral_baselines` migration — rebased onto a single
linear chain, re-verified zero schema drift against every model).

Weaknesses found and fixed during the merge, matching the standard set
this audit applies to every module:

- **No rate limiting on the endpoint that makes a real outbound HTTP
  call.** `sync_cve` could block a worker thread for
  `NVD_TIMEOUT_SECONDS` and could be used to hammer NVD's own API.
  Extracted the previously auth-router-only `Limiter` into
  `app/core/rate_limit.py` so it's a genuinely shared instance (not a
  second independent one) and applied `THREAT_INTEL_SYNC_RATE_LIMIT`
  (10/minute default) the same way `LOGIN_RATE_LIMIT` already protects
  `/auth/login`.
- **CVE ID validation only checked a prefix** (`startswith("CVE-")`),
  not a real shape — tightened to a proper `CVE-YYYY-NNNN` regex so a
  malformed ID fails cleanly here instead of risking a raw DB error
  from exceeding the `cve_id` column's length or sending a malformed
  query to NVD.
- **The vulnerability list endpoint computed its total by loading every
  matching row into memory** (`len(list(...))`) on every call — a real
  resource-exhaustion vector given NVD's actual CVE volume (200,000+
  records). Replaced with a SQL-side `COUNT`.
- **No ceiling on the stored raw provider payload.** `raw_data` is an
  unbounded `Text` column; added a defensive truncation (200KB) so one
  unexpectedly large or malformed provider response can't cause
  unbounded row growth.
- **A malformed CVSS score from the provider would raise an unhandled
  exception** (bare `float(score)`) instead of degrading gracefully —
  wrapped defensively, since a provider response is still external,
  untrusted input regardless of how reliable NVD normally is.
- Found and fixed a genuine bug in the module's own test fixture (not
  a hardening issue): the "did this CVE change" test asserted a score
  change should be detected as `updated=True`, but the fixture never
  varied `raw_data` — the actual field the service compares — so the
  test was failing before any of the above changes too. Confirmed by
  running the original upload's test in isolation first. Fixed the
  fixture to vary `raw_data` consistently with `cvss_score`, matching
  how real NVD data behaves (the score is always extracted from that
  same payload).

222 -> 237 backend tests. Live-verified against a running server: the
full request chain (auth -> RBAC -> disabled-by-default check -> the
new endpoints) boots and behaves correctly end-to-end, not just under
pytest.

## Update: 2026-09-14 — Simulation Mode

Domain 14 is implemented. `app/simulation/` lets an Admin generate a
small, self-contained demo scenario (2 synthetic assets on the RFC 5737
TEST-NET-2 documentation range, 2 synthetic events using real
detection-rule event types) and immediately runs the unmodified
`DetectionEngine` against it, so alerts appear right away through the
exact same pipeline real data goes through -- not a separate "fake
alert" path. `POST /api/v1/simulation/reset` cleanly purges every
synthetic row in FK-safe order.

Building this surfaced that the domain's core promise -- "simulation
data must never be mixed silently with production data" -- was not
actually enforced anywhere before now, even though the hooks existed:

- `Alert` and `Incident` already had `is_synthetic` columns (migrated),
  but nothing ever set them. `DetectionEngine` hardcoded
  `is_synthetic=False` on every alert regardless of whether the
  triggering event was synthetic. Fixed: `Finding` now carries
  `is_synthetic`, computed from whether every contributing event is
  synthetic (a mix is treated as real -- never rounded up to
  synthetic), and `AlertService.upsert_from_finding` uses it instead of
  a hardcoded value.
- The alert dedup key was `rule_key:asset_id` -- a synthetic finding
  for the same rule+asset as a real one would have silently merged
  into (and extended the evidence trail of) the real alert, or vice
  versa. The key now includes real/simulated status, so they can never
  collide.
- `IncidentService.create_incident` hardcoded `is_synthetic=False`.
  Fixed to derive it from the linked alerts/assets -- and, since a
  derived flag when the inputs disagree is itself a way to silently
  mix data, creating an incident from a mix of real and simulated
  alerts/assets is now rejected outright (`IncidentError`) rather than
  guessed at.
- `Asset` was the one entity in the pipeline with no `is_synthetic`
  column at all. Added via migration `6efc6543c092`; verified upgrade
  and downgrade both apply cleanly and zero schema drift against every
  model, same rigor as every migration this audit has added.
- No list endpoint (assets, alerts, incidents) filtered on
  `is_synthetic` at all -- simulated data would have shown up mixed
  into ordinary views the moment any of it existed. Added
  `include_synthetic` (default `False`) to all three.
- Found and fixed the same `len(list(...))`-for-counting inefficiency
  in the assets repository as was already fixed once in threat-intel
  (`app/assets/repository.py`) -- flagging repeated patterns like this
  suggests it's worth grep'ing for `len(list(self.db.scalars(` across
  the rest of the codebase at some point rather than fixing it
  module-by-module as each one is touched.

251 backend tests passing (up from 237). Live-verified against a
running server end-to-end: run -> alerts generated -> excluded from
normal list views -> visible with include_synthetic=true -> reset ->
status returns to inactive.

Still open: Authorized Device Management, Device Management Agent
Architecture (domains 11-12 -- a real device-agent protocol, not yet
started), and an Identity integration boundary (SSO/LDAP-style external
identity, distinct from the app's own login system).

## Update: 2026-09-18 — Device Management + Agent Architecture

Domains 11-12 are implemented as a bounded first slice: enrollment,
policy-gated task queueing, an agent poll/report protocol, and a
reference agent that proves the whole loop works end-to-end.

`app/device_management/` adds `ManagedDevice` (1:1 with `Asset` --
most assets are never enrolled; enrollment is a deliberate admin
action, not automatic) and `DeviceTask`. The spec's own diagram
("Authorization check -> Action policy engine -> device") is enforced
literally in `service.py`'s `queue_task()`: role check first, then
per-action-type confirm requirement, before a task is ever created --
not just documented.

- Agent authentication is a genuinely separate mechanism from the
  JWT/User/Role system (`app/device_management/agent_auth.py`) --
  a distinct trust boundary, not a second implementation of the same
  subsystem. Agent tokens are high-entropy random values hashed with
  SHA-256 for indexed lookup (`app/device_management/tokens.py`),
  deliberately not bcrypt/`hash_password()` -- that's for low-entropy
  human passwords where slow, salted hashing defends against offline
  brute force; a 32-byte random token doesn't need that, and bcrypt's
  per-call salting would make an indexed lookup-by-token impossible.
- Enrollment is two-step and never trusts the network alone: an admin
  issues a single-use, 15-minute enrollment token through the human
  Control API; only that token can mint the durable agent credential,
  shown to the operator exactly once.
- `DeviceActionType` is a closed enum (`status_check`,
  `inventory_sync`, `service_restart`, `reboot`, `isolate`) -- not a
  generic command string. The spec explicitly warns against exactly
  that ("agents must not silently execute arbitrary instructions").
- `reboot`/`isolate` require both an Admin-tier role and an explicit
  `confirm=true` -- verified live: attempting either without confirm
  returns 403 before a task is ever created.
- Completing a state-changing action (`service_restart`/`reboot`/
  `isolate`) emits a `NetworkEvent` (reusing `EventSource.MANUAL` --
  a dedicated `DEVICE_MANAGEMENT` source value was considered but
  skipped: adding a Postgres enum value needs `ALTER TYPE ... ADD
  VALUE`, which has real transaction-boundary restrictions I couldn't
  verify against a live Postgres instance in this sandbox; noted as a
  reasonable follow-up rather than risking an untested migration).
  Read-only actions (`status_check`/`inventory_sync`) do not.
- `scripts/reference_agent.py` is a real, working reference
  implementation of the agent protocol (poll, execute, report) --
  used to verify the entire flow against an actually-running server,
  not just pytest: enroll -> agent redeems token -> admin queues
  status_check -> agent executes and reports -> admin queues reboot
  without confirm (403) -> queues again with confirm -> agent executes
  (simulated, the reference agent never performs a real destructive
  action) -> task shows completed -> exactly one NetworkEvent exists,
  from the reboot, not the status_check. It deliberately never performs
  a real reboot/isolate/service-restart -- reports success with a
  "simulated" result string, so it's safe to run against a real
  machine as a protocol demonstration.
- Revoking a device (`POST .../revoke`) clears the agent token hash
  immediately; verified live that a revoked token stops authenticating
  on the very next request.

251 -> 271 backend tests passing.

Still open, deliberately not attempted this pass: real OS-level task
execution (the reference agent simulates destructive actions rather
than performing them -- a real agent binary per platform is a much
larger, separate undertaking), a dedicated `DEVICE_MANAGEMENT` event
source (see above), and a frontend UI for any of this (per the
"UI will eventually follow" direction from the prior session).
Identity integration (SSO/LDAP) remains the one fully untouched domain
from the original 15.
