# VEXUS — AI-Powered Network Security Intelligence Platform

**Status: V1 complete, V2 in progress.**

V1 phases 1–8 (Foundation, Discover, Watch, Nexus, Detect, Risk, Trace,
AI) are implemented, tested, and have a working UI. Post-V1 work has
added Sense (behavioral baselines), Simulation, Device Management
(enrollment, agent protocol, UI), and Discovery Scan Profiles, plus
three V2 foundations: Background Scheduler, External Event Ingestion,
and Threat Intelligence (NVD CVE feed).

**The authoritative status record is
`docs/architecture/V2_ARCHITECTURE_AUDIT.md`** — every V2 addition is
documented there with dated, verified test counts. The vision and
development rules live in `docs/vexus-v2.md`.

Do not treat anything beyond what's described below as production-ready
without your own review — see "Known limitations" at the bottom.

---

## What's implemented

**Phase 1 — Foundation:** JWT auth, RBAC (Admin / Security Analyst /
Network Administrator / Viewer), audit logging, the VEXUS Data Contract,
VEXUS Health.

**Phase 2 — Discover:** authorized-only network discovery (refuses scans
outside `AUTHORIZED_SCAN_RANGES`), asset inventory, new/changed-asset
detection.

**Phase 3 — Watch:** active availability/latency/packet-loss monitoring
(Windows- and Unix-compatible), historical metrics, missing-asset
detection.

**Phase 4 — Nexus:** asset relationships with mandatory confidence
classification (confirmed/inferred) — manual links and subnet inference
only; no traffic-based relationships, since VEXUS captures no network
traffic anywhere.

**Phase 5 — Detect:** 5 rule-based detectors turning `NetworkEvent`s
into deduplicated, tunable `Alert`s. Alert dedup/suppression and
per-rule configuration live in the database (`DetectionRuleConfig`) —
thresholds can be tuned without a redeploy.

**Phase 6 — Risk:** explainable scoring. Every score is a sum of named,
visible factors (criticality, trust status, active alerts), stored
individually so any score can be traced back to its inputs.

**Phase 7 — Trace:** incident investigation. Analyst-created incidents
linking alerts/assets as evidence, a timeline assembled entirely from
real evidence, append-only investigation notes, full status workflow.

**Phase 8 — AI:**
- `AIProvider` abstraction: `NullProvider` (default — the platform works
  fully with AI disabled), `AnthropicProvider` (real HTTP integration
  against `api.anthropic.com`), and an Ollama-backed local path
  (`AI_PROVIDER=local`) for payment-free operation.
- **Structured output is enforced, not just prompted.** The model must
  return JSON matching `{observed_facts, inferences, hypotheses,
  recommendations, confidence}`; the response is Pydantic-validated
  before it reaches any caller. Malformed output raises an error — it's
  never passed through or silently patched.
- Context sent to the model is deliberately minimal: only already-
  surfaced fields (alert/asset/incident summaries), never a raw DB dump.
- Every query is logged (`AIQueryLog`) — the audit trail and the history
  the UI reads from, so repeat views don't re-call the API.
- Three entry points: explain an alert, summarize an incident, ask a
  free-form question grounded in a specific alert/incident/asset.

**Phase 9 — Sense:** behavioral baselines and anomaly detection.
Statistical baselines per asset; `SenseService.evaluate_all_assets()`
wired into the scheduler loop.

**Phase 10 — Simulation:** emits synthetic `NetworkEvent`s tagged
`event_source="simulation"` and `is_synthetic=true`. The flag is
non-nullable and propagates through `Finding` → `Alert` → `Incident` →
`Asset`, so simulated data can never be displayed as real telemetry.
List endpoints exclude synthetic data by default (`include_synthetic=false`).
`POST /api/v1/simulation/reset` purges every synthetic row in FK-safe order.

**Phase 11 — Device Management:** `ManagedDevice` (1:1 with `Asset`) and
`DeviceTask`. Two-step enrollment (single-use, 15-minute token mints a
durable agent credential). Agent authentication is a separate trust
boundary from the JWT/User/Role system — high-entropy tokens hashed with
SHA-256 for indexed lookup. `DeviceActionType` is a closed enum
(`status_check`, `inventory_sync`, `service_restart`, `reboot`,
`isolate`). Destructive actions require Admin role **and** explicit
`confirm=true`. `scripts/reference_agent.py` is a real, working protocol
implementation for end-to-end verification. Full frontend UI in
`DeviceManagement.tsx` (enrollment, task queueing, revoke).

**Phase 12 — Discovery Scan Profiles:** `NmapCollector` uses a
closed-enum `ScanProfile` instead of free-form arguments:
- `HOST_DISCOVERY` — `-sn`, legacy ping-scan behavior
- `STEALTH_SYN` — `-sS -T3`, TCP SYN half-open (**new platform default**)
- `SERVICE_VERSION` — adds `-sV` banner grabbing
- `OS_DETECT` — adds `-O` TCP/IP stack fingerprinting
- `FULL` — `-sS -sV -O`, slowest

Profile is selectable per scan (`ScanRequest.profile`), persisted on
every `ScanJob` (including refused scans, for audit), and surfaced in
the scan history UI.

---

## V2 foundations (shipped)

**Background Scheduler:** `app/core/scheduler.py` — in-process asyncio
scheduler (no new infrastructure dependency). Off by default
(`SCHEDULER_ENABLED=false`). Each job type runs on its own independent
loop and interval, so one slow or failing job cannot block the others.
Reuses the exact same service methods as manual triggers — no second
implementation of any behavior. `HealthService` reports live status per
worker, automatically downgrading to `degraded` if the last success is
more than 15 minutes old.

**External Event Ingestion:** `POST /api/v1/events/ingest` accepts a
batch of externally-sourced events (`event_source` ∈ `{syslog,
threat_intel, manual}`). Assets are resolved by IP; unmatched IPs store
the event with `asset_id=null` rather than discarding. Batches are
all-or-nothing. Ingested events flow through the unmodified detection
pipeline.

**Threat Intelligence (NVD CVE feed):** `app/threat_intel/` — NVD 2.0
CVE API adapter. `POST /api/v1/threat-intel/sync/cve/{id}` fetches and
normalizes a CVE into a `vulnerabilities` table and emits a
`NetworkEvent` through the same event contract. Off by default
(`NVD_ENABLED=false`). Rate-limited (`THREAT_INTEL_SYNC_RATE_LIMIT`,
10/minute default).

**VEXUS Correlate:** read-only incident candidates, produced by grouping
active, unsuppressed alerts on the same asset within a configurable time
window. Candidates are projections only — analysts still create
incidents through the existing Trace workflow.

---

## Documentation map

- **`README.md`** (this file) — current state, quick start, honest limitations.
- **`docs/architecture/PHASE0_ARCHITECTURE.md`** — the original V1
  foundation document. Design decisions, module shape, security model.
- **`docs/architecture/V2_ARCHITECTURE_AUDIT.md`** — the running audit
  trail. Every V2 addition is documented here with the actual test count,
  honest findings, and things fixed during implementation. **This is the
  authoritative record of what is actually implemented and tested, dated
  per update.**
- **`docs/vexus-v2.md`** — the V2 vision and development rules. Defines
  the 15 functional domains, the layered architecture, and the rules the
  codebase is held to. **Not a status tracker** — its roadmap section is
  a stale planning snapshot by its own disclaimer; use the audit doc for
  status.
- **`docs/KNOWLEDGE_TRANSFER.md`** — onboarding context for a new
  contributor or a future session.

---

## Windows / Termux compatibility notes

`PingCollector` (Watch) detects the OS and uses correct `ping` syntax for
Windows and Linux/macOS/Termux. `NmapCollector` (Discover) assumes `nmap`
is on `PATH` and hasn't been Windows-adapted.

---

## Quick start (local dev, no Docker)

### Backend — macOS/Linux/Termux

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
```

Edit .env:

· SECRET_KEY — required. Generate one:
  python -c "import secrets; print(secrets.token_urlsafe(64))".
  There is no default; a missing value fails at startup rather than
  silently signing JWTs with a public key.
· AUTHORIZED_SCAN_RANGES — optional. Discovery refuses to scan
  outside these ranges. Entries broader than a /8 are rejected with a
  logged warning (so 0.0.0.0/0 cannot accidentally authorize the whole
  internet).

For a payment-free AI assistant, install Ollama and pull a local model:

```bash
ollama pull llama3.2:3b
```

Then set AI_PROVIDER=local in .env and restart the backend. VEXUS
uses Ollama at http://127.0.0.1:11434 by default. Change
LOCAL_AI_MODEL to use a different installed model.

Discovery uses DISCOVERY_COLLECTOR=auto by default: Nmap when
available, falling back to the dependency-free Python TCP collector. Set
DISCOVERY_COLLECTOR=python to force the fallback, or =nmap to require
Nmap. The Python collector checks the ports in DISCOVERY_PORTS (default:
22,80,443,445,3389,8000,8080), so it can miss hosts with no listening
service on those ports.

Discovery scan technique is controlled by DISCOVERY_DEFAULT_PROFILE
(default stealth_syn). A malformed value is surfaced as a 400 at scan
time, never silently falls back.

```bash
python3 -m alembic upgrade head

export VEXUS_ADMIN_USERNAME=admin
export VEXUS_ADMIN_EMAIL=admin@vexus.local
export VEXUS_ADMIN_PASSWORD=<choose-a-strong-password>
python3 -m scripts.seed

uvicorn app.main:app --reload
```

Backend — Windows (PowerShell)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy ..\.env.example .env
```

Edit .env the same way, then:

```powershell
python -m alembic upgrade head
$env:VEXUS_ADMIN_USERNAME="admin"
$env:VEXUS_ADMIN_EMAIL="admin@vexus.local"
$env:VEXUS_ADMIN_PASSWORD="<choose-a-strong-password>"
python -m scripts.seed
uvicorn app.main:app --reload
```

API docs (any OS): http://localhost:8000/docs

Frontend (same on all platforms)

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:5173

Tests

```bash
cd backend
python3 -m pytest tests/ -q
```

285 backend tests passing. Coverage spans every module: auth, RBAC,
discovery (including scan profiles), monitoring (cross-platform ping
parsing), topology, detection/alerting, risk scoring, incident
investigation, device management (including the agent auth boundary),
threat intelligence, simulation, sense, scheduler, and AI (pure
request/response functions, service-level with an injected fake
provider, and full API-level RBAC).

End-to-end verification

scripts/e2e_check.py runs a live 15-step chain against a running
server: admin login → discovery with explicit profile → discovery with
default profile → invalid profile rejected → device enrollment → agent
redeems token → task queueing → confirm-gated destructive action →
agent poll/report → revoke → revoked token rejected. This is run
manually by an operator; the test suite does not exercise a live nmap
binary or destructive device actions.

---

Quick start (Docker Compose)

```bash
cp .env.example .env
docker compose up --build
```

---

Project structure

```
vexus/
├── backend/    FastAPI app (see backend/app/<domain>/ for each module)
├── frontend/   React + TS + Tailwind
├── docs/       Architecture, V2 audit, knowledge transfer, roadmap
└── docker-compose.yml
```

Each backend domain is a self-contained module with the same internal
shape: router.py (thin), schemas.py (Pydantic), service.py
(application logic), domain.py (pure business rules, no I/O),
repository.py (SQLAlchemy only), models.py (ORM). This keeps
business logic testable without spinning up FastAPI or a DB, and keeps
detection logic independent from AI.

---

Security notes

· AUTHORIZED_SCAN_RANGES in .env is empty by default. Discovery
  refuses to scan anything outside explicitly authorized CIDR ranges.
  Entries broader than a /8 are rejected with a logged warning.
· Monitoring only actively probes (ICMP ping) assets already in the
  inventory with a known IP.
· AI context is minimal by design — never a raw network/DB dump.
· SECRET_KEY has no default; a missing value fails at startup.
· Agent credentials are high-entropy tokens hashed with SHA-256,
  deliberately not bcrypt — bcrypt's per-call salting makes indexed
  lookup-by-token impossible, and a 32-byte random token doesn't need
  slow hashing.
· External event ingestion rejects event_source values that could
  impersonate first-party subsystems (discovery, monitoring) or
  simulation.
· Audit log writes are append-only at the repository level; no update or
  delete methods are exposed for that table.
· Never commit a real .env.

---

Known limitations (honest, not hidden)

· Live AI HTTP path untested against a real paid key. The local
  Ollama path (AI_PROVIDER=local) is the tested, payment-free route.
  Cloud providers (AI_PROVIDER=cloud / deepseek) require paid API
  access and have not been exercised end-to-end in this environment.
· PythonTcpCollector only discovers hosts accepting TCP connections on
  its configured probe ports; it cannot reliably find silent hosts
  without ICMP, ARP, or Nmap.
· NmapCollector's live path and PingCollector's Windows path have
  been exercised manually, not in an automated test environment. The
  test_nmap_scan_profiles.py tests assert on the assembled argument
  list, not on nmap execution (running nmap in CI would require the
  binary plus a real target).
· Real OS-level task execution on managed devices is not
  implemented. scripts/reference_agent.py proves the protocol but
  deliberately simulates destructive actions (reboot, isolate,
  service_restart) rather than performing them.
· No dedicated DEVICE_MANAGEMENT event source. Completed
  device-management actions emit events under EventSource.MANUAL.
  Adding a new Postgres enum value requires ALTER TYPE ... ADD VALUE,
  which has transaction-boundary restrictions that weren't verified
  against live Postgres in this environment.
· Identity integration (SSO/LDAP-style external identity) is the one
  fully untouched domain from the original 15. The app has its own
  login system; there's no boundary for an external identity provider
  yet.
· Vulnerability data is not wired into risk scoring yet. The
  vulnerabilities table exists (populated by the threat-intel sync);
  the risk engine doesn't consume it.
· Nexus has no traffic-based relationships anywhere in the platform.
· Detect implements 5 of 8 originally-designed rules (no port-exposure,
  connection-failure, or traffic-volume detection — no data source
  exists for any of them yet).
· Risk implements 3 of 5 originally-envisioned factor categories (no
  vulnerability data, no behavioral-anomaly baselines wired in).
· SQLite path selection is process-directory dependent for local
  development. Normalizing development startup around one path is an
  open item.
· Frontend automated tests are not configured beyond TypeScript and
  build validation.
· The migration chain uses the documented Alembic create_type=False
  pattern for enum reuse, but this has not been executed against live
  Postgres in this environment.

---

What's next (V2)

The remaining named gaps, per the audit doc's dated entries:

· Identity integration — SSO/LDAP-style external identity.
· Real OS-level agent task execution — a per-platform agent binary.
· A dedicated DEVICE_MANAGEMENT event source.
· Wiring vulnerability data into risk scoring.

Development is governed by the rules in docs/vexus-v2.md — most
importantly: no duplicating subsystems, no hardcoded mock data as
production functionality, no marking features complete unless tests pass
and the flow is verified live, and update the docs when architectural
decisions change.

See docs/architecture/V2_ARCHITECTURE_AUDIT.md for the full audit
trail and docs/vexus-v2.md for the roadmap.
