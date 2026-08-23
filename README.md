# VEXUS

**AI-Powered Network Security Intelligence Platform**

VEXUS observes a network, tracks its assets, detects anomalies, scores risk, and helps a security analyst investigate what's happening — with every conclusion traceable back to real evidence. No fabricated detections, no relationships VEXUS can't back up, no AI output presented as fact.

Built for authorized defensive security use: monitoring, inventory, and incident investigation on networks you own or are explicitly authorized to assess. Not an offensive tool — no exploitation, credential harvesting, or automated attack capability exists anywhere in the codebase.

## Status

V1 complete — all 8 planned modules implemented and tested (154 backend tests). See [Known limitations](#known-limitations) for what's intentionally out of scope and why.

| Module | What it does |
|---|---|
| **Foundation** | JWT auth, role-based access control, audit logging |
| **Discover** | Authorized-only network scanning, asset inventory, change detection |
| **Watch** | Availability/latency monitoring, missing-asset detection |
| **Nexus** | Asset relationships (manual + subnet-inferred), confidence-labeled |
| **Detect** | Rule-based detection engine → deduplicated, tunable alerts |
| **Risk** | Explainable 0–100 scoring — every point traced to a named factor |
| **Trace** | Incident investigation: evidence linking, timeline, notes |
| **AI** | Assistant that explains alerts/incidents from VEXUS's own data |

## Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL/SQLite
- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **Infra:** Docker Compose (Postgres + Redis + backend + frontend)

## Quick start

### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp ../.env.example .env
```
Edit `.env` — set `SECRET_KEY` (`python -c "import secrets; print(secrets.token_urlsafe(64))"`). Optionally set `AUTHORIZED_SCAN_RANGES` to enable real scans, or `AI_PROVIDER=cloud` + `ANTHROPIC_API_KEY` to enable the AI assistant.

```bash
python3 -m alembic upgrade head

export VEXUS_ADMIN_USERNAME=admin
export VEXUS_ADMIN_EMAIL=admin@vexus.local
export VEXUS_ADMIN_PASSWORD=<choose-a-strong-password>
python3 -m scripts.seed

uvicorn app.main:app --reload
```
API docs: `http://localhost:8000/docs`

### Frontend
```bash
cd frontend
npm install
npm run dev
```
App: `http://localhost:5173`

### Docker Compose (alternative)
```bash
cp .env.example .env   # set SECRET_KEY and admin vars first
docker compose up --build
```

### Tests
```bash
cd backend
python3 -m pytest tests/ -v
```

## Architecture

Full system diagram, ER design, security model, and the module-by-module design rationale live in [`docs/architecture/`](docs/architecture).

Core principles enforced throughout the codebase, not just documented:
- **Evidence First** — no detection, risk score, or AI response exists without a traceable link back to raw observed data.
- **Confidence-aware** — severity, confidence, and risk are always tracked separately, never conflated.
- **Read-only** — VEXUS observes and recommends; it never takes automated action on the network.
- **Self-aware** — the platform monitors its own worker health and flags stale/incomplete data rather than presenting it as current.

## Known limitations

Stated here rather than discovered later:

- **No background scheduler.** Discovery, monitoring, detection, and risk scoring all run on-demand (triggered via the UI/API), not on a timer. Each has a pluggable collector/provider interface, so wiring in a real worker loop later doesn't require a rewrite.
- **Nmap-based discovery and the live AI API call are implemented but not exercised against real infrastructure** in the environment this was built in — verify both before relying on them.
- **Detect** implements 5 of 8 originally-scoped rule types (no port-exposure, connection-failure, or traffic-volume detection — none have a real data source yet).
- **Risk** scores from criticality, trust status, and active alerts only — no vulnerability feed or behavioral-baseline integration exists yet.
- **Trace** has no automatic incident correlation; every incident is analyst-created. Multi-alert auto-correlation is future scope.
- **Nexus** has no traffic-based relationships — VEXUS doesn't capture network traffic anywhere in the current build.

## License

MIT — see [LICENSE](LICENSE).
