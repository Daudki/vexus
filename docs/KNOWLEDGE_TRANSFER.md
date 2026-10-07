# VEXUS — Knowledge Transfer

Everything accumulated across the development sessions that built this out. Read this instead of asking where something is or how something works — it's all here.

---

## 1. What this is

VEXUS is a full-stack internal network security operations platform. Backend: FastAPI + SQLAlchemy + Alembic + Pydantic v2, SQLite for dev / Postgres for prod. Frontend: React + TypeScript + Vite + Tailwind.

Two documents already live in the repo and stay authoritative for scope/status — this document is the "how it actually works and why" layer underneath them:

- `docs/vexus-v2.md` — the original vision/spec. 15 functional domains. Treat its roadmap checkboxes as stale; they were never kept in sync with real progress.
- `docs/architecture/V2_ARCHITECTURE_AUDIT.md` — dated, running log of what's actually verified working, what's broken, what's missing. Every session's work gets an entry appended here. **This is the source of truth for "is X actually done," not the spec's checkboxes.**

---

## 2. Directory map

**Backend** (`backend/app/`), one module per domain, each typically has `models.py`, `schemas.py`, `service.py` (or `repository.py`, or both), `router.py`:

| Module | What it owns |
|---|---|
| `auth` | Login, JWT issuance/refresh, rate-limited login |
| `users` | User/Role CRUD, RBAC role definitions |
| `assets` | Asset inventory (the "what devices exist" table) and per-asset detected services (`AssetNetworkService`) |
| `discovery` | Active network scanning (nmap or Python-TCP fallback), scope enforcement |
| `monitoring` | Passive polling (ping/latency) of known assets |
| `events` | `NetworkEvent` — the central data contract; also the external ingestion boundary (`POST /events/ingest` for syslog/threat-intel/manual sources) |
| `detection` | Turns `NetworkEvent`s into `Alert`s via rule evaluation |
| `alerts` | Alert CRUD, status workflow, assignment |
| `correlation` | **Read-only** candidate grouping of alerts by asset+time — does NOT create incidents itself |
| `incidents` | Analyst-driven incident creation from alerts/assets, investigation notes, timeline |
| `risk` | Risk scoring for assets: criticality, trust, active alerts, and linked vulnerabilities (`AssetVulnerability`, owned by `threat_intel`) |
| `topology` | Asset relationship graph (manual + inferred links) |
| `sense` | Behavioral baselines (mean/stddev of monitoring metrics) + anomaly evaluation |
| `threat_intel` | NVD CVE feed adapter — `Vulnerability` records, manual per-CVE sync; asset-to-CVE links (`AssetVulnerability`) and CPE matching of detected services (`matching.py`) |
| `simulation` | Demo-data generator — creates a self-contained fake scenario that flows through the real detection pipeline |
| `admin` | Scan-range config, system stats dashboard (NOT user management — that's in `users`) |
| `device_management` | Authorized device enrollment + agent protocol (poll/report). Separate auth boundary from the human JWT system — see §14 |
| `audit` | `AuditLog` — every sensitive action writes here |
| `health` | `/health/` — DB connectivity + per-worker heartbeat status |
| `ai` | AI assistant (Anthropic + DeepSeek providers, both wired) — explain-alert, summarize-incident |
| `common` | Shared small models (`DataQualityWarning`) |
| `core` | Cross-cutting: `deps.py` (RBAC dependencies), `security.py` (hashing/JWT), `scheduler.py` (background loops), `rate_limit.py` (shared slowapi `Limiter`) |
| `database` | `base.py` (declarative base + `UUIDPrimaryKeyMixin`/`TimestampMixin`), `session.py` (engine + `get_db`) |
| `config` | `settings.py` — the one `Settings` class, `.env`-driven |

**Frontend** (`frontend/src/`):

- `pages/` — one file per route: `Landing`, `Login`, `Dashboard`, `Assets`, `AssetDetail`, `Discovery`, `Topology`, `Alerts`, `Incidents`, `IncidentDetail`, `ThreatIntel`, `AdminPanel`, `AIWorkspace`
- `services/` — one file per backend module's API client (`assets.ts`, `alerts.ts`, `admin.ts`, `threatIntel.ts`, etc.), all going through `services/api.ts`'s `apiRequest()` helper
- `components/` — `Layout.tsx` (nav shell + `NAV_ITEMS` array), `AdminLayout.tsx`/`AdminRoute.tsx` (admin-only gate), `ui/` (Button, Card, Badge, Form)
- `hooks/useAuth.tsx` — the auth context; `user.role` is what you check for RBAC-aware UI

---

## 3. The data spine — understand this before anything else

Everything flows through one table: `NetworkEvent` (`app/events/models.py`). Its own docstring says it plainly: *"Every module that observes something... writes a NetworkEvent in this exact shape. Nothing downstream (Detection, Correlation, Risk) reads from any other table."*

```
DISCOVERY ─┐
MONITORING ─┤
EVENTS API  ├──► NetworkEvent ──► DetectionEngine.run() ──► Alert ──► (analyst creates) ──► Incident
THREAT_INTEL┤         (rules.py)                                           ▲
SIMULATION ─┘                                                    CORRELATION (read-only
                                                                   candidate suggestions,
                                                                   never auto-creates)
```

- `EventSource` enum: `discovery | monitoring | syslog | threat_intel | identity | simulation | manual`. `identity` is reserved (no writer exists yet — identity integration isn't built).
- `DetectionEngine.run()` (`app/detection/service.py`) pulls unprocessed events, runs each registered `DetectionRule` (`app/detection/rules.py`), turns `Finding`s into `Alert`s via `AlertService.upsert_from_finding()`. This is on-demand (`POST /detection/run`) or scheduled (see §7).
- Rules are keyed by `event_type` strings: `NEW_DEVICE`, `IP_CHANGED`, `MAC_CHANGED`, `AVAILABILITY_ANOMALY`, `ASSET_MISSING`. If you want a new detection, add a rule here with a matching `event_type`, and make sure something upstream writes events with that exact string.
- Incidents are **never** auto-created. `app/correlation/` only *suggests* groupings; an analyst always explicitly calls `POST /incidents` with the alert/asset IDs they've decided belong together.

---

## 4. RBAC — how permission checks actually work

Four roles (`app/users/models.py` `RoleName`): `ADMIN`, `SECURITY_ANALYST`, `NETWORK_ADMINISTRATOR`, `VIEWER`. Enum member names are uppercase (matches the Postgres enum label), values are lowercase (`admin`, `security_analyst`, ...) — that's what's actually sent over the wire in the JWT and to the frontend.

Two dependency helpers, both in `app/core/deps.py`:
- `require_role(RoleName.ADMIN, RoleName.SECURITY_ANALYST, ...)` — variadic, any one of the listed roles passes.
- `require_any_role` — any authenticated, active user, regardless of role.

Every router endpoint uses one of these via `Depends(...)`. I individually audited every router endpoint once (see the audit doc's "RBAC coverage" entry) — it's solid. If you add a new endpoint, pick the tighter of the two deliberately; don't default to `require_any_role` out of laziness for something that mutates data.

---

## 5. Security decisions and why

- **`SECRET_KEY` has no default.** It used to (`"dev-secret-key-change-me"`), which was a real vulnerability — since this is a public repo, that string was public, so any deployment that forgot to set it was silently forgeable. Now `Settings()` construction fails loudly (`ValidationError`) if it's unset. Tests provide their own throwaway value in `conftest.py` (`os.environ.setdefault(...)` at the very top, before any `app.*` import — order matters, since importing `app.main` transitively constructs `Settings()`).
- **`VEXUS_ADMIN_PASSWORD` has no hardcoded fallback either.** `scripts/seed.py` generates and prints a random one if you don't set it, rather than defaulting to a known password.
- **`AUTHORIZED_SCAN_RANGES` has a ceiling.** Nothing stops an admin from typing `0.0.0.0/0` and authorizing the entire internet — so `app/discovery/scope.py` rejects (with a logged warning, not a crash) anything broader than `/8`. `10.0.0.0/8` (the whole RFC1918 10.x block) still works — that's a deliberate boundary choice, not an accident.
- **Login is rate-limited** (`LOGIN_RATE_LIMIT`, default `5/minute`), and so is threat-intel's CVE sync (`THREAT_INTEL_SYNC_RATE_LIMIT`, default `10/minute` — it makes a real outbound HTTP call and can block a worker thread). Both share **one** `Limiter` instance (`app/core/rate_limit.py`) — don't create a second `Limiter()` anywhere; extend the shared one.
- **CORS** is an explicit origin allowlist (`CORS_ORIGINS`, comma-separated — not JSON-array syntax, that was a real bug once), never wildcarded.
- **SQLite doesn't enforce foreign keys by default**, unlike Postgres. `app/database/session.py` explicitly turns it on (`PRAGMA foreign_keys=ON` via a `connect` event listener) so dev/SQLite behavior matches prod/Postgres behavior — without this, deleting something referenced elsewhere would silently orphan rows in dev while correctly failing in prod.

---

## 6. Migrations — the single most dangerous recurring bug class

**The test suite bootstraps its schema via `Base.metadata.create_all()`, not via Alembic.** This means tests passing proves nothing about whether `alembic upgrade head` on a real fresh database actually produces a working schema. I found this exact bug **twice**: `behavioral_baselines` (Sense module) and it nearly happened again with the threat-intel merge (a migration fork, not a missing migration, but same root cause — untested migration chain).

**Before trusting any migration work, run this check** (adjust the model imports to whatever's current):

```python
from sqlalchemy import create_engine, inspect
from app.database.base import Base
import app.ai.models, app.alerts.models, app.assets.models, app.audit.models, app.common.models
import app.detection.models, app.discovery.models, app.events.models, app.health.models
import app.incidents.models, app.monitoring.models, app.risk.models, app.sense.models
import app.topology.models, app.users.models, app.threat_intel.models  # keep this list current

engine = create_engine("sqlite:///./check.db")
inspector = inspect(engine)
actual = set(inspector.get_table_names())
expected = set(Base.metadata.tables.keys())
print("Missing:", expected - actual)
print("Extra:", actual - expected - {"alembic_version"})
for t in sorted(expected & actual):
    exp_cols = {c.name for c in Base.metadata.tables[t].columns}
    act_cols = {c["name"] for c in inspector.get_columns(t)}
    if exp_cols != act_cols:
        print(f"DRIFT {t}: model-only={exp_cols-act_cols} db-only={act_cols-exp_cols}")
```

Run `alembic upgrade head` against a genuinely fresh SQLite file first, then run the above against that same file. Also always test `alembic downgrade -1` then `upgrade head` again — cheap insurance.

**Postgres-specific gotcha**: if two migrations create separate tables that both use the same named `sa.Enum(...)`/`postgresql.ENUM(...)` (e.g. `metrictype` used by both `monitoring_samples` and `behavioral_baselines`), the second migration must pass `create_type=False`, or Postgres will error trying to `CREATE TYPE` something that already exists. SQLite doesn't have this concept at all, so SQLite-only testing won't catch it. A real Postgres 16 is now available in the sandbox (`apt-get update`, then `apt-get install -y postgresql`, then `pg_ctlcluster 16 main start`; the earlier install failure was a stale package index). The full migration chain was verified against it on 2026-10-07: upgrade, `alembic check` with zero differences, downgrade to base, and re-upgrade. Run that cycle on both SQLite and Postgres for any new migration, because `alembic check` on SQLite hides type, timezone and constraint differences.

**Migration fork check**: `alembic heads` should always print exactly one line. If it prints two, two migrations were written against the same `down_revision` in parallel (this happened once, merging independently-developed branches) — fix by editing one migration's `down_revision` to point after the other instead.

---

## 7. Background scheduler

`app/core/scheduler.py` — a plain asyncio loop, no Celery/APScheduler. **Off by default** (`SCHEDULER_ENABLED=false`). This is deliberate, not an oversight: the test suite triggers FastAPI's lifespan (`with TestClient(app) as client`), so if the scheduler defaulted on, every test run would spin up real background loops against whatever `DATABASE_URL` happens to be configured for the test process.

Reuses the exact same service methods the manual "run now" endpoints call — `MonitoringService.poll_all()`, `DetectionEngine.run()`, `DiscoveryService.run_scan()`, `SenseService.evaluate_all_assets()`. One independent asyncio task per job type, so a slow one (discovery) never blocks the others. Discovery only auto-schedules if `AUTHORIZED_SCAN_RANGES` is actually configured.

`GET /health/` reports real per-worker status now (`monitoring`/`discovery`/`detection`/`sense`) — `unknown` if a cycle has never run, `ok`/`degraded` from the worker's own `WorkerHeartbeat` row, auto-downgraded to `degraded` if the last success is >15 minutes old even if the last recorded status was `ok`.

---

## 8. Simulation Mode — the `is_synthetic` contract

This is easy to get wrong, so understand the rule precisely: **a mix of real and simulated data is never silently rounded either direction.**

- `NetworkEvent`, `Alert`, `Incident`, `Asset` all carry `is_synthetic: bool`.
- A `Finding` is synthetic only if **every** contributing event is synthetic (computed in `DetectionEngine.run()`, not per-rule).
- The alert dedup key is `f"{rule_key}:{asset_id}:{'sim' if is_synthetic else 'real'}"` — this is why: without the suffix, a simulated finding for the same rule+asset as a real one would silently merge into (and extend the evidence trail of) the real alert.
- `IncidentService.create_incident()` **refuses outright** (raises `IncidentError`) if the given alerts/assets mix real and synthetic — it does not try to derive a "best guess" flag.
- Every list endpoint (`/assets`, `/alerts`, `/incidents`) defaults to excluding synthetic rows; pass `include_synthetic=true` to see them.
- `app/simulation/service.py`'s `run_scenario()` creates fake assets on `198.51.100.0/24` (RFC 5737 TEST-NET-2 — reserved for documentation/examples, structurally impossible to collide with a real discovered host) and writes events using **real** rule-matching `event_type` strings, then calls the real `DetectionEngine.run()` — so simulated alerts go through the identical code path real ones do. `reset()` deletes everything synthetic in FK-safe order (link tables → incidents → alerts → events → asset history → assets).

If you ever add a new entity that can be created from alert/asset data, it needs to follow this same pattern: carry `is_synthetic`, derive it from inputs (never hardcode `False`), and reject mixed inputs rather than guess.

---

## 9. Recurring bug pattern to watch for

**`len(list(self.db.scalars(query)))` used to compute a count.** This loads every matching row into memory just to count them — a real resource-exhaustion risk at scale (threat-intel has 200,000+ real CVEs to eventually sync). I found and fixed this **three separate times** independently (`threat_intel/repository.py`, `assets/repository.py`) before noting it as a pattern rather than one-off bugs. If you're ever debugging a slow list endpoint, grep for this exact pattern across `app/*/repository.py` first — it likely hasn't been fully eradicated. The fix is always the same: `self.db.scalar(select(func.count()).select_from(query.subquery()))`.

---

## 10. Testing conventions

- `tests/conftest.py`: `client` and `db_session` fixtures. `db_session` is a fresh in-memory SQLite DB per test (via `Base.metadata.create_all`, not Alembic — see §6). `client` overrides `get_db` to use that same session, and calls `app.state.limiter.reset()` per test since slowapi's rate-limit storage is process-global and would otherwise leak between tests.
- Settings that read env vars need `from app.config.settings import get_settings; get_settings().cache_clear()` (it's `@lru_cache`d) both before `monkeypatch.setenv(...)` and after the test, or the cached value leaks into later tests.
- Rate-limit values (`LOGIN_RATE_LIMIT`, `THREAT_INTEL_SYNC_RATE_LIMIT`) are read **once, at router import time** (module-level `settings = get_settings()`), not per-request — so a test can't override them via `monkeypatch.setenv` after the app has already imported. To test rate limiting, just exceed the real configured default.
- Async tests (the scheduler) use `@pytest.mark.asyncio` with `pytest-asyncio`'s default strict mode — no special config needed, it's already a pinned dependency.
- Before trusting any test run, periodically run it with **zero local `.env` file** and a **fresh venv** — `backend/.env` is gitignored (confirmed), so a real fresh clone/CI never has one; a lingering local `.env` from earlier manual testing can mask a genuine "this breaks on a clean checkout" bug (this is exactly how the `SECRET_KEY` default removal got verified as actually complete).

---

## 11. Known environment gotchas

- **npm install can fail** with `Cannot read properties of null (reading 'edgesOut')` — a real npm 10.9.7 + vitest 4.x arborist bug, unrelated to any code change. Fix: `npm install --legacy-peer-deps`.
- **Pydantic v2 field validators don't run on default values** unless the field is declared with `Field(default=None, validate_default=True)`. Bit once: a `timestamp: Optional[datetime] = None` field with a validator meant to default it to `now()` silently stayed `None` when the caller omitted it entirely, because the validator never fired.
- **React fragment shorthand (`<>...</>`) can't carry a `key` prop.** When mapping a list to fragments (e.g. a table row + an expandable detail row per item), you need `<Fragment key={...}>` (imported explicitly) or `<React.Fragment key={...}>` — the shorthand syntax has no way to accept one.
- **Alembic + SQLite**: SQLite has very limited native `ALTER COLUMN` support. `op.add_column` works fine natively; anything that needs `alter_column` (changing a default, type, nullability after creation) generally needs `op.batch_alter_table(...)` for SQLite portability. Simplest avoidance: don't write migrations that need `alter_column` if you can help it — e.g. a `server_default` that stays forever is fine, don't bother dropping it later just for cosmetic cleanliness.

---

## 12. Running things locally

```bash
cd backend
cp ../.env.example .env          # then edit SECRET_KEY (generate: python -c "import secrets; print(secrets.token_urlsafe(64))")
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m scripts.seed            # creates roles + an admin user (or set VEXUS_ADMIN_* env vars first)
uvicorn app.main:app --reload

# separately:
cd frontend
npm install --legacy-peer-deps
npm run dev
```

Full test suite: `cd backend && python -m pytest tests/ -q` (currently 323 tests, all passing).

---

## 13. What's built vs. not (as of this document)

**Working, tested, live-verified** (not just "file exists"): Auth/RBAC, Asset Intelligence, Discovery, Monitoring (+ scheduler), Event Contract (+ external ingestion boundary), Detection, Alerts, Correlation (read-only), Incidents, Risk, Topology (basic), Sense (baselines/anomalies), AI Assistant (Anthropic + DeepSeek), Health Monitoring (real per-worker status), Threat Intelligence (NVD CVE feed), Simulation Mode, Device Management + Agent Protocol (enrollment, policy-gated tasks, a working reference agent — see §14).

**Not started at all:**
- **Identity integration** — SSO/LDAP-style external identity, distinct from Vexus's own login system. `EventSource.IDENTITY` exists as a reserved enum value; nothing writes it. This is now the only fully untouched domain from the original 15.
- **Frontend automated tests** — currently just a TypeScript build check, no real test suite (Vitest is a dependency but unused).
- **No UI for device management, threat intel sync (frontend for it exists), simulation, or admin overview** beyond what's already been built — device management in particular has zero frontend right now.
- **Real OS-level agent execution** — the reference agent (`scripts/reference_agent.py`) simulates destructive actions rather than performing them. A real per-platform agent binary is a separate, larger undertaking.
- A dedicated `EventSource.DEVICE_MANAGEMENT` value (currently reusing `MANUAL`) — skipped because adding a Postgres enum value via `ALTER TYPE ... ADD VALUE` has real transaction-boundary restrictions never verified against a live Postgres in this environment.
- SQLite dev path is working-directory-dependent — a known fragility, not yet fixed.

If picking up more work: read the tail of `docs/architecture/V2_ARCHITECTURE_AUDIT.md` first (each session appends a dated entry), then decide the next slice.

---

## 14. Device Management + Agent Protocol — a second auth boundary

`app/device_management/` — the only part of the codebase with authentication that is *not* the JWT/User/Role system. Understand this before touching it:

- `ManagedDevice` is 1:1 with `Asset` (FK, unique). Most assets are never enrolled — enrollment is a deliberate admin action (`POST /device-management/devices/{asset_id}/enroll`, ADMIN only), not automatic.
- Two-step credential issuance: admin issues a single-use, 15-minute **enrollment token**; only that token can be redeemed (`POST /agent/enroll`) to mint the durable **agent token**, shown to the operator exactly once. Both hashed with SHA-256 (`app/device_management/tokens.py`) — deliberately *not* `hash_password()`/bcrypt. Bcrypt's per-call salting means you can't look up a row by "does this hash match," only by re-verifying against one already-known row (fine for login: look up by username first). A bearer token has no separate identifier to look up by, so it needs a deterministic hash for an indexed exact-match query — bcrypt's slowness is also pointless here since the token's own 32-byte entropy, not hash cost, is what resists brute force.
- `app/device_management/agent_auth.py`'s `get_current_agent` is the parallel to `get_current_user` — a completely separate dependency, checked via `Authorization: Bearer <agent_token>` same as human requests, but resolved against `ManagedDevice.agent_token_hash`, not a `User`/JWT.
- The policy engine (`ACTION_POLICY` in `service.py`) is checked in `queue_task()` before a task is ever created — role tier per `DeviceActionType`, plus `reboot`/`isolate` require both Admin and explicit `confirm=true`. `DeviceActionType` is a closed enum, not a free-form command string — adding a new action is a code change.
- Agents never execute anything the server tells them via a generic mechanism: they poll `GET /agent/tasks/next`, execute locally, and report via `POST /agent/tasks/{id}/result`. `scripts/reference_agent.py` is a real, runnable reference implementation — useful for testing the protocol against a live server without a real managed machine. It deliberately simulates destructive actions (reboot/isolate/service_restart) rather than performing them; only `status_check`/`inventory_sync` do anything real (safe local introspection).
- Completing a state-changing action emits a `NetworkEvent` (currently tagged `EventSource.MANUAL` — a dedicated source value was skipped because adding a Postgres enum value needs `ALTER TYPE ... ADD VALUE`, untested against real Postgres in this environment; a reasonable follow-up, not done yet).
- Revoking a device (`POST .../revoke`) clears the agent token hash immediately — the credential stops working on the very next request, not eventually.
