# VEXUS — Phase 0 Architecture
### AI-Powered Network Security Intelligence Platform (V1 Foundation)

---

## 1. Product Architecture

VEXUS V1 is a single-tenant defensive security intelligence platform for a network the operator owns or is explicitly authorized to monitor. The product is organized around a data pipeline, not a feature list:

```
Discover assets → Watch behavior → Detect anomalies → Correlate into incidents
→ Score risk → Investigate (Trace) → Explain (AI) → Recommend (Response)
```

Every later stage consumes structured output from the stage before it. Nothing downstream fabricates data — if a stage has no evidence, it produces nothing rather than a guess.

V1 scope = items 1–15 from the brief (auth, RBAC, discovery, monitoring, topology, events, detection, alerts, risk, incidents, audit, AI assistant, dashboard). Sense (ML baselines), Correlate (multi-signal incident synthesis), and Response (automated action) get *interfaces* in V1 but only basic/manual implementations.

---

## 2. System Architecture (Diagram)

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (SPA)                        │
│        React + TS — Dashboard / SOC View / Settings          │
└───────────────────────────┬────────────────────────────────┘
                             │ REST (JSON) + JWT
┌───────────────────────────▼────────────────────────────────┐
│                        FastAPI Backend                       │
│  API Layer → Application Services → Domain Logic → Repos     │
│                                                                │
│  auth · users · assets · discovery · monitoring · topology   │
│  events · detection · alerts · incidents · risk · audit · ai │
└───────┬───────────────────────────────────────┬─────────────┘
        │                                       │
┌───────▼────────┐                    ┌─────────▼──────────┐
│ PostgreSQL      │                    │ Background Workers   │
│ (SQLite in dev) │                    │ (discovery scans,    │
│                 │                    │  monitoring polls)   │
└─────────────────┘                    └─────────┬────────────┘
                                                  │
                                        ┌─────────▼─────────┐
                                        │ Redis (job queue,   │
                                        │ rate-limit, cache)  │
                                        └─────────────────────┘
                                                  │
                                        ┌─────────▼─────────┐
                                        │ AIService abstraction│
                                        │ Cloud LLM / Local LLM│
                                        └─────────────────────┘
```

Redis and background workers are justified specifically by discovery scans and monitoring polls needing to run off the request thread — not added speculatively.

---

## 3. Component Architecture

Each backend domain (`assets`, `discovery`, `detection`, etc.) is a self-contained module with the same internal shape:

```
module/
├── router.py       # FastAPI routes — thin, no business logic
├── schemas.py      # Pydantic request/response models
├── service.py       # Application logic, orchestration
├── domain.py        # Pure business rules (testable, no I/O)
├── repository.py    # SQLAlchemy queries only
└── models.py         # ORM models
```

This keeps `RULE 9` (business logic independent from UI) and `RULE 10` (detection logic independent from AI) structurally enforced rather than just a convention.

---

## 4. Backend Architecture

- **FastAPI** app factory pattern; each module registers its own router via `APIRouter`.
- **Dependency injection** for DB sessions, current user, and permission checks — no global state.
- **Domain layer is framework-agnostic**: detection rules and risk scoring are plain Python functions/classes that take structured input and return structured output, so they're unit-testable without spinning up FastAPI or a DB.
- **Extension points** built as Python `Protocol` interfaces from day one:
  - `DiscoveryCollector` (nmap today; future SNMP/agent-based collectors)
  - `MonitoringCollector` (ping/latency today; future SNMP, flow data)
  - `DetectionRule` (each rule is a class implementing `evaluate(events) -> Finding[]`)
  - `AIProvider` (Cloud/Local, per section 16)
  - `RiskFactor` (pluggable scoring contributors)

---

## 5. Frontend Architecture

- React + TypeScript + Vite + Tailwind, feature-folder structure (`features/assets`, `features/alerts`, etc.) mirroring backend domains.
- `services/` — typed API clients per domain.
- Shared `types/` generated/kept in sync with backend Pydantic schemas to avoid drift.
- SOC View is the primary navigation spine: Dashboard → Alert → Asset → Events → Timeline → Incident → AI Analysis → Recommendation, implemented as a single investigation route with contextual side panels rather than disconnected pages.

---

## 6. Database ER Design (core entities)

```
User ──< AuditLog
User ──< Incident (assigned_to)
Role ──< User

Asset ──< AssetHistory
Asset ──< NetworkEvent
Asset ──< AssetRelationship (source/target, confidence)

NetworkEvent ──< Alert (via evidence linkage)
DetectionRule ──< Alert
Alert }──< Incident (many-to-many via IncidentAlert)
Asset }──< Incident (many-to-many via IncidentAsset)
Incident ──< InvestigationNote

Asset ──< RiskScore ──< RiskFactor (contributing factors, explainable)
```

Key normalization decisions:
- `NetworkEvent` is the single normalized ingestion point — discovery, monitoring, and detection all *write* events; nothing else. This keeps the evidence trail consistent regardless of source.
- `RiskFactor` rows are individually stored (not just a final number) so every score is explainable per section 13.
- `AssetRelationship.confidence` is an enum (`confirmed | inferred | unknown`), never omitted.

---

## 7. API Architecture

- REST, versioned under `/api/v1/`.
- Resource-oriented routes per domain: `/assets`, `/events`, `/alerts`, `/incidents`, `/risk`, `/topology`, `/ai/*`.
- Consistent envelope for list endpoints (pagination, filtering, sorting) since assets/events/alerts all need it.
- `/ai/ask` accepts a structured context reference (asset id, alert id, incident id) rather than free-text-only, so the AI layer always operates on VEXUS data, not just a prompt.
- OpenAPI docs auto-generated by FastAPI serve as the living API documentation (section 23).

---

## 8. Security Architecture

- Auth: JWT access + refresh tokens, password hashing via `bcrypt`/`argon2`.
- RBAC enforced via FastAPI dependency (`require_role(...)`) checked at the router layer before any service call.
- Input validation via Pydantic on every boundary; SQLAlchemy ORM (no raw string SQL) for injection protection.
- CORS restricted to known frontend origin(s); secure headers middleware (HSTS, X-Content-Type-Options, etc.).
- Rate limiting on auth endpoints specifically (brute-force protection) via Redis.
- Secrets only via environment variables, `.env.example` provided, `.env` gitignored.
- Audit log writes are append-only at the repository level (no update/delete methods exposed for that table).
- Discovery module: explicit target-scope validation against an "authorized ranges" allowlist before any scan can run; every scan logs who/when/scope.

---

## 9. Detection Pipeline

```
Raw signal (discovery / monitoring / log)
        ↓
NetworkEvent (normalized, stored)
        ↓
DetectionRule.evaluate() — independent, pluggable modules
        ↓
Finding { evidence[], severity, confidence }
        ↓
Alert (created if finding crosses threshold)
        ↓
[Future: Correlate] Alert clustering → Incident Candidate
        ↓
Incident (analyst-confirmed or auto-created from strong correlation)
```

Severity and confidence are tracked as separate fields throughout — never conflated into one score.

---

## 10. AI Architecture

```
AIService (interface)
    ├── CloudLLMProvider   (external API, redacted/minimized payload)
    └── LocalLLMProvider    (future, on-prem)
```

- AI only ever receives *structured summaries* of VEXUS data (asset metadata, event evidence, risk factors) that the service layer prepares — never raw DB access, never full network dumps.
- Response schema enforces the Observed Fact / Inference / Hypothesis / Recommendation distinction from section 15 — this is a Pydantic-validated output shape, not just prompt instruction, so malformed or overconfident responses are rejected before reaching the UI.
- The rest of the platform (detection, risk, alerts) works fully with `AIService` disabled — it's an enrichment layer, never a dependency.

---

## 11. V1 / V2 / V3 Feature Boundaries

| Version | Scope |
|---|---|
| **V1** | Auth/RBAC, Discover, Watch, basic Nexus (manual+inferred topology), Detect (rule-based), basic Risk, Trace, audit, AI assistant (explain/summarize on existing data), dashboard |
| **V2** | Sense (statistical baselines), Correlate (multi-signal incident synthesis), threat intel (CVE/NVD) integration, SIEM/syslog ingestion |
| **V3** | Identity integrations, controlled Response automation, VEXUS Lab (simulation), Mobile, multi-tenant, advanced graph analytics (centrality, lateral-movement path inference) |

---

## 12. Repository Structure

Matches the structure given in the brief as-is — it's already well-factored (domain-per-folder backend, feature-per-folder frontend, docs/scripts/docker at root). No changes recommended; I'll use it verbatim unless a specific domain needs a subfolder later (e.g., `detection/rules/` for individual rule modules).

---

## 13. Development Roadmap

Phase 1 (Foundation) → 2 (Discover) → 3 (Watch) → 4 (Nexus) → 5 (Detect) → 6 (Risk) → 7 (Trace) → 8 (AI), exactly as specified in the brief. Each phase ends with passing tests before the next starts (RULE 3).

---

## 13.5 Architectural Additions (accepted)

These are now binding architectural rules for V1, not future aspirations.

**VEXUS Data Contract.** Every source (discovery, monitoring, and eventually syslog/threat-intel/identity) normalizes into one `NetworkEvent` shape before anything else touches it: `event_id, event_type, event_source, timestamp, asset_id, source_asset_id, destination_asset_id, severity, confidence, evidence, metadata, correlation_id, parent_event_id`. `correlation_id`/`parent_event_id` are added now (unused until Correlate ships) specifically so V2 doesn't require a schema migration to retrofit them.

**Evidence First.** No detection, risk score, incident, or AI explanation exists without a traceable evidence chain back to a raw `NetworkEvent`. Enforced at the model level: `Finding`, `Alert`, `RiskFactor`, and AI responses all carry a non-nullable evidence reference, not just free text.

**Severity vs. Confidence vs. Risk.** Three independent fields, never derived from one another. Severity = potential damage if true. Confidence = how sure VEXUS is the detection is accurate. Risk = severity + confidence + asset context (criticality, exposure, history) combined explicitly in the `RiskFactor` breakdown.

**Alert deduplication/suppression — moved into V1.** `Alert` gets a `dedup_key` (rule + asset + signature) and a `count`/`first_seen`/`last_seen`. Repeats within a rule's suppression window increment the existing alert instead of creating a new one. Analysts can acknowledge, suppress, whitelist, or mark false-positive per dedup group.

**Detection Rule Management — moved into V1.** Rule *logic* stays code (a `DetectionRule` class), but `enabled`, `severity`, `confidence_threshold`, `alert_threshold`, and `suppression_window` live in a `DetectionRuleConfig` table. Analysts tune rules without a redeploy.

**Read-Only First.** V1 has zero code paths that mutate the network. Every detection terminates in a `Recommendation`, never an action. This is enforced by simply not building an action-execution module yet — there's nothing to disable.

**Explainability Layer — first-class, not an AI feature.** A dedicated `explainability` service assembles the WHY-chain (event → rule → evidence → severity/confidence → asset risk → recommendation) as structured data. AI reads and narrates this; it does not generate it. This is what keeps RULE 11 (AI never replaces deterministic controls) architecturally true rather than just a promise.

**Simulation Mode — added to V1.** A `simulation` module can emit synthetic `NetworkEvent`s tagged `event_source="simulation"` and `is_synthetic=true`. The flag is non-nullable and propagates through Finding/Alert/Incident so simulated data can never be displayed or queried as if it were real telemetry. This is how the full pipeline gets tested end-to-end without a live network.

**VEXUS Health.** A `health` module tracks worker heartbeats (discovery, monitoring), Redis connectivity, DB connectivity, last successful scan/poll timestamps, and AI provider availability. Dashboard surfaces this as a simple status strip (🟢/🟡/🔴) — this is what section 17's dashboard now leads with, above the security metrics, since a security platform that's silently blind is worse than one that's honest about it.

**Data Quality.** Any module that produces a result under degraded conditions (monitoring gap, unidentified OS, low sample size for a baseline) attaches a `DataQualityWarning` to that result rather than presenting it as complete. Surfaced inline wherever the affected data is shown (asset page, risk breakdown, dashboard).

### Revised core principles (7)
1. Evidence First — no evidence, no conclusion.
2. Explainable — every decision has a traceable reason.
3. Confidence-Aware — confidence, severity, and risk are separate.
4. Event-Driven — everything flows through the VEXUS Data Contract.
5. Human-Controlled — V1 observes and recommends; humans act.
6. Modular — every collector/detector/provider is replaceable.
7. Self-Aware — VEXUS monitors its own health and data quality.

These reshape the ER diagram in section 6 (add `dedup_key`/`count` to `Alert`, add `DetectionRuleConfig`, add `is_synthetic` to `NetworkEvent`, add `DataQualityWarning`, add a `WorkerHeartbeat`/`HealthStatus` table) and the pipeline diagram in section 9 to insert Correlation and Explainability as explicit stages. Implementation picks these up starting in Phase 1 (Health, data contract, simulation scaffolding) even though Correlate itself is still V2.

---

## 14. Key Architectural Risks

1. **Discovery scope creep** — an nmap-backed scanner is easy to accidentally point at the wrong range. Mitigation: hard allowlist of authorized CIDR ranges enforced server-side, not just UI-side.
2. **Event volume growth** — `NetworkEvent` will grow fast once monitoring polls run continuously. Needs indexing strategy and retention policy decided before Phase 3, not after.
3. **AI over-trust** — biggest product risk is a user treating an AI "Inference" as an "Observed Fact." Mitigation is the enforced structured-output schema (section 10), not just prompt wording.
4. **Topology confidence inflation** — inferred relationships (e.g., "these two talk a lot") can look authoritative in a graph UI. Mitigation: confidence-based visual styling (dashed vs. solid edges) is a Phase 4 requirement, not optional polish.
5. **Risk score gaming/drift** — if `RiskFactor` weights are hardcoded, they'll need re-tuning per-network. Store weights as configurable data, not constants, from the start.

---

## 15. Recommended Improvements to the Brief

- Add a lightweight **retention/rollup policy** for `NetworkEvent` and metrics history to the Watch module scope now, so it's not a painful retrofit.
- Define the **allowlisted scan range** as a first-class DB entity in Phase 1 (not Phase 2), since Discover depends on it existing and it's also a security control worth auditing from day one.
- Add a minimal **rule config table** for `DetectionRule` thresholds in Phase 5 so severity/confidence tuning doesn't require redeploys.
- Consider deferring full topology **visualization** (force-directed graph rendering) to late Phase 4 and shipping a simple adjacency list/table view first — de-risks the phase without blocking backend work.

---

**Awaiting approval before starting Phase 1 (Foundation).**
