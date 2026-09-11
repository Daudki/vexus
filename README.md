# VEXUS — AI-Powered Network Security Intelligence Platform

**Status: V1 complete — all 8 phases** (Foundation, Discover, Watch,
Nexus, Detect, Risk, Trace, AI). Every module from the original V1
scope is implemented, tested, and has a working UI.

Do not treat anything beyond what's described below as production-ready
without your own review — see "Known limitations" at the bottom.

## What's implemented

**Phase 1 — Foundation:** JWT auth, RBAC (Admin / Security Analyst /
Network Administrator / Viewer), audit logging, the VEXUS Data
Contract, VEXUS Health.

**Phase 2 — Discover:** authorized-only network discovery (refuses
scans outside `AUTHORIZED_SCAN_RANGES`), asset inventory,
new/changed-asset detection.

**Phase 3 — Watch:** active availability/latency/packet-loss
monitoring (Windows- and Unix-compatible), historical metrics,
missing-asset detection.

**Phase 4 — Nexus:** asset relationships with mandatory confidence
classification (confirmed/inferred) — manual links and subnet
inference only; no traffic-based relationships, since VEXUS captures
no network traffic anywhere.

**Phase 5 — Detect:** 5 rule-based detectors turning `NetworkEvent`s
into deduplicated, tunable `Alert`s.

**Phase 6 — Risk:** explainable scoring — every score is a sum of
named, visible factors (criticality, trust status, active alerts).

**Phase 7 — Trace:** incident investigation — analyst-created
incidents linking alerts/assets as evidence, a timeline assembled
entirely from real evidence, append-only investigation notes, full
status workflow.

**Phase 8 — AI:**
- `AIProvider` abstraction: `NullProvider` (default — the platform
  works fully with AI disabled) and `AnthropicProvider` (real HTTP
  integration against `api.anthropic.com`).
- **Structured output is enforced, not just prompted.** The model must
  return JSON matching `{observed_facts, inferences, hypotheses,
  recommendations, confidence}`; the response is Pydantic-validated
  before it reaches any caller. Malformed output raises an error —
  it's never passed through or silently patched.
- Context sent to the model is deliberately minimal: only
  already-surfaced fields (alert/asset/incident summaries), never a raw
  DB dump.
- Every query is logged (`AIQueryLog`) — the audit trail and the
  history the UI reads from, so repeat views don't re-call the API.
- Three entry points: explain an alert, summarize an incident, ask a
  free-form question grounded in a specific alert/incident/asset.
- **Honest limitation:** the pure request-building and response-parsing
  logic is fully unit-tested (9 tests covering valid responses,
  malformed JSON, schema violations, multi-block responses, missing
  content). The live HTTP call to Anthropic's API has not been
  exercised against a real key in this environment — verify before
  relying on it.

## Windows / Termux compatibility notes

`PingCollector` (Watch) detects the OS and uses correct `ping` syntax
for Windows and Linux/macOS/Termux. `NmapCollector` (Discover) assumes
`nmap` is on `PATH` and hasn't been Windows-adapted.

## Quick start (local dev, no Docker)

### Backend — macOS/Linux/Termux
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
```
Edit `.env`: set a real `SECRET_KEY`
(`python -c "import secrets; print(secrets.token_urlsafe(64))"`).
Optionally set `AUTHORIZED_SCAN_RANGES` (to run real scans). For a
payment-free AI assistant, install Ollama for Windows, start it, and
download a local model:

```powershell
ollama pull llama3.2:3b
```

Then set `AI_PROVIDER=local` in `.env` and restart the backend. VEXUS
uses Ollama at `http://127.0.0.1:11434` by default. You can change
`LOCAL_AI_MODEL` to another model already installed in Ollama. Cloud
options (`AI_PROVIDER=cloud` or `deepseek`) remain available when paid
API access is configured.

Discovery uses `DISCOVERY_COLLECTOR=auto` by default: it uses Nmap when
available and falls back to the dependency-free Python TCP collector when
Nmap is unavailable. Set `DISCOVERY_COLLECTOR=python` to force the fallback,
or `DISCOVERY_COLLECTOR=nmap` to require Nmap. The Python collector checks
the ports in `DISCOVERY_PORTS` (default: `22,80,443,445,3389,8000,8080`),
so it can miss hosts with no listening service on those ports; Nmap remains
the better choice for broad host discovery and metadata.

```bash
python3 -m alembic upgrade head

export VEXUS_ADMIN_USERNAME=admin
export VEXUS_ADMIN_EMAIL=admin@vexus.local
export VEXUS_ADMIN_PASSWORD=<choose-a-strong-password>
python3 -m scripts.seed

uvicorn app.main:app --reload
```

### Backend — Windows (PowerShell)
```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy ..\.env.example .env
```
Edit `.env` the same way, then:
```powershell
python -m alembic upgrade head
$env:VEXUS_ADMIN_USERNAME="admin"
$env:VEXUS_ADMIN_EMAIL="admin@vexus.local"
$env:VEXUS_ADMIN_PASSWORD="<choose-a-strong-password>"
python -m scripts.seed
uvicorn app.main:app --reload
```

API docs (any OS): http://localhost:8000/docs

### Frontend (same on all platforms)
```bash
cd frontend
npm install
npm run dev
```
App: http://localhost:5173

### Tests
```bash
cd backend
python3 -m pytest tests/ -v
```
154 tests covering every module: auth, RBAC, discovery, monitoring
(cross-platform ping parsing), topology, detection/alerting, risk
scoring, incident investigation, and AI (pure request/response
functions, service-level with an injected fake provider, and full
API-level RBAC).

## Quick start (Docker Compose)

```bash
cp .env.example .env
docker compose up --build
```

## Project structure

See `docs/architecture/` for the full architecture document.

```
vexus/
├── backend/    FastAPI app (see backend/app/<domain>/ for each module)
├── frontend/   React + TS + Tailwind
├── docs/       Architecture doc (docs/architecture/)
└── docker-compose.yml
```

## Security notes

- `AUTHORIZED_SCAN_RANGES` in `.env` is empty by default. Discovery
  refuses to scan anything outside explicitly authorized CIDR ranges.
- Monitoring only actively probes (ICMP ping) assets already in the
  inventory with a known IP.
- AI context is minimal by design — never a raw network/DB dump.
- Never commit a real `.env`.

## Known limitations (honest, not hidden)

- **No background job scheduler.** Discovery, monitoring, detection,
  risk, and AI all run synchronously when triggered via the UI/API —
  set up your own external scheduler (cron, Task Scheduler, Termux's
  `cron`) to hit those endpoints periodically. The provider
  abstractions throughout (`DiscoveryCollector`, `MonitoringCollector`,
  `AIProvider`) are exactly what a real worker loop would call, so
  adding one later isn't a rewrite.
- `PythonTcpCollector` only discovers hosts accepting TCP connections on
  its configured probe ports; it cannot reliably find silent hosts without
  ICMP, ARP, or Nmap.
- `NmapCollector`, `PingCollector`'s Windows path, and
  `AnthropicProvider`'s live HTTP call are real implementations that
  haven't been exercised against real external systems in this dev
  environment — verify each before relying on it in production.
- Nexus has no traffic-based relationships anywhere in the platform.
- Detect implements 5 of 8 originally-designed rules (no port-exposure,
  connection-failure, or traffic-volume detection — no data source
  exists for any of them yet).
- Risk implements 3 of 5 originally-envisioned factor categories (no
  vulnerability data, no behavioral-anomaly baselines).
- Trace has no automatic incident-candidate generation — that's VEXUS
  Correlate, explicitly deferred to V2.
- AI has no local-model provider yet, only cloud (Anthropic).

## What's next (V2, per the architecture doc)

VEXUS Correlate now exposes read-only incident candidates by grouping
active, unsuppressed alerts on the same asset within a bounded time
window. Candidates remain projections until an analyst creates an
incident, preserving the V1 human-confirmation boundary. The remaining
next steps are threat intelligence (CVE/NVD), SIEM/syslog ingestion,
identity integrations, and a real background worker/scheduler — each
one fills a gap explicitly called out above, rather than being a new,
disconnected direction.
