VEXUS v2

«VEXUS — Veil + Nexus
A modular network intelligence, security monitoring, and authorized infrastructure management platform.»

"VEXUS" (./docs/assets/vexus-logo.png)

---

Project Vision

VEXUS v2 is the next major evolution of the VEXUS platform.

The platform is designed to provide a unified environment for:

- Network discovery
- Asset intelligence
- Network monitoring
- Security event collection
- Threat and anomaly detection
- Incident correlation
- Risk assessment
- Network topology visualization
- AI-assisted investigation
- Authorized device administration and management
- Security simulation
- System health monitoring

VEXUS should evolve into a network intelligence control platform, not merely a dashboard that displays security data.

The long-term objective is:

DISCOVER
    ↓
UNDERSTAND
    ↓
MONITOR
    ↓
DETECT
    ↓
CORRELATE
    ↓
INVESTIGATE
    ↓
EXPLAIN
    ↓
RESPOND
    ↓
MANAGE AUTHORIZED INFRASTRUCTURE

---

Core Principle

VEXUS is an intelligence layer over a network.

The platform should continuously answer questions such as:

- What devices exist on this network?
- What services are they exposing?
- How are devices connected?
- What changed?
- What behavior is unusual?
- What assets present the highest risk?
- Which security events are related?
- What incidents are developing?
- What is happening on the network right now?
- What authorized administrative actions can be performed safely?

---

VEXUS v2 Development Rules

IMPORTANT FOR COPILOT AND FUTURE DEVELOPMENT

Before implementing any feature:

1. Inspect the existing architecture.
2. Reuse established abstractions where appropriate.
3. Do not duplicate existing models or services.
4. Do not introduce a second implementation of the same subsystem.
5. Prefer modular services over large monolithic files.
6. Keep security-sensitive operations explicitly separated from ordinary application logic.
7. Do not hardcode mock data as production functionality.
8. Do not mark features as complete unless they actually work.
9. Test the implementation before considering the feature complete.
10. Update documentation when architectural decisions change.

Do not do this:

Feature request
    ↓
Random new file
    ↓
Random route
    ↓
Random database model
    ↓
Duplicate logic

Preferred process:

Feature request
    ↓
Inspect existing architecture
    ↓
Identify affected domain
    ↓
Extend existing abstractions
    ↓
Implement service logic
    ↓
Expose API
    ↓
Connect frontend
    ↓
Test
    ↓
Document

---

Architecture Overview

VEXUS follows a layered architecture.

┌───────────────────────────────────────────────┐
│                 FRONTEND                      │
│                                               │
│ React + TypeScript                            │
│ Dashboard                                     │
│ Network Visualization                         │
│ Asset Intelligence                            │
│ Security Operations                           │
│ Device Management                             │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│                  API LAYER                    │
│                                               │
│ FastAPI                                       │
│ Authentication                                │
│ RBAC                                          │
│ Validation                                    │
│ API Versioning                                │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│                SERVICE LAYER                  │
│                                               │
│ Discovery                                     │
│ Monitoring                                    │
│ Detection                                     │
│ Correlation                                   │
│ Risk                                          │
│ Investigation                                 │
│ Response                                      │
│ Device Management                             │
└───────────────────────┬───────────────────────┘
                        │
             ┌──────────┴──────────┐
             ▼                     ▼
┌─────────────────────┐   ┌─────────────────────┐
│    DATA LAYER       │   │    INTEGRATIONS     │
│                     │   │                     │
│ PostgreSQL          │   │ Network Scanners    │
│ Redis               │   │ Monitoring Agents   │
│ Event Storage       │   │ Authorized Agents   │
│ Audit Logs          │   │ External APIs       │
└─────────────────────┘   └─────────────────────┘

---

Recommended Project Structure

The existing project structure should be preserved where practical, but development should move toward the following architecture.

vexus/
│
├── backend/
│   │
│   ├── app/
│   │   │
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   └── dependencies.py
│   │   │
│   │   ├── core/
│   │   │   ├── security.py
│   │   │   ├── logging.py
│   │   │   └── exceptions.py
│   │   │
│   │   ├── config/
│   │   │   └── settings.py
│   │   │
│   │   ├── database/
│   │   │   ├── session.py
│   │   │   └── base.py
│   │   │
│   │   ├── auth/
│   │   ├── users/
│   │   ├── assets/
│   │   ├── discovery/
│   │   ├── monitoring/
│   │   ├── topology/
│   │   ├── events/
│   │   ├── detection/
│   │   ├── alerts/
│   │   ├── incidents/
│   │   ├── risk/
│   │   ├── investigation/
│   │   ├── response/
│   │   ├── device_management/
│   │   ├── integrations/
│   │   ├── audit/
│   │   ├── ai/
│   │   ├── simulation/
│   │   ├── health/
│   │   │
│   │   └── main.py
│   │
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
│   │
│   ├── src/
│   │   ├── components/
│   │   ├── features/
│   │   ├── pages/
│   │   ├── layouts/
│   │   ├── services/
│   │   ├── hooks/
│   │   ├── contexts/
│   │   ├── types/
│   │   └── utils/
│   │
│   └── package.json
│
├── docs/
│   ├── architecture/
│   ├── api/
│   ├── security/
│   └── development/
│
├── scripts/
├── docker-compose.yml
├── .env.example
└── README.md

---

Technology Stack

Backend

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Alembic
- Redis
- Pydantic

Frontend

- React
- TypeScript
- Vite
- React Router
- TanStack Query

Infrastructure

- Docker
- Docker Compose

Network Intelligence

Integrations should remain modular and replaceable.

Examples include:

- Authorized network discovery tools
- Network monitoring agents
- Syslog sources
- SNMP-enabled infrastructure
- Approved device-management agents
- Security event sources

Do not tightly couple the entire platform to a single external tool.

---

VEXUS v2 Functional Domains

1. Authentication and Identity

The platform must provide:

- Secure authentication
- Access tokens
- Refresh tokens
- User management
- Role-based access control
- Permission-based authorization
- Account security
- Authentication audit logs

Default Roles

Administrator
Security Analyst
Network Administrator
Viewer

Permissions should be granular.

Example:

assets:read
assets:scan

alerts:read
alerts:update

incidents:read
incidents:update

devices:read
devices:manage

topology:read

settings:read
settings:manage

Do not rely exclusively on frontend permission checks.

All sensitive authorization must be enforced by the backend.

---

2. Asset Intelligence

The asset system is one of the foundations of VEXUS.

Every discovered or registered device should have an asset identity.

An asset may include:

ID
Hostname
IP addresses
MAC address
Operating system
Device type
Vendor
Services
Open ports
Network location
First seen
Last seen
Status
Risk score
Tags
Metadata

Example:

{
  "id": "asset-123",
  "hostname": "server-01",
  "ip_addresses": ["192.168.1.20"],
  "mac_address": "AA:BB:CC:DD:EE:FF",
  "device_type": "server",
  "status": "online",
  "risk_score": 72
}

Asset history must be preserved.

The system should be able to identify:

- New devices
- Devices disappearing from the network
- IP changes
- Service changes
- Port changes
- Identity changes
- Significant risk changes

---

3. Network Discovery

Discovery must be designed around explicit authorization and configured network scope.

The discovery pipeline should be:

AUTHORIZED TARGET SCOPE
        ↓
NETWORK DISCOVERY
        ↓
HOST IDENTIFICATION
        ↓
SERVICE ENUMERATION
        ↓
ASSET NORMALIZATION
        ↓
ASSET COMPARISON
        ↓
CHANGE DETECTION
        ↓
EVENT GENERATION

Discovery must never assume that every reachable network is an authorized target.

Discovery Features

- Authorized scan ranges
- Scan profiles
- Scheduled discovery
- Manual discovery
- Asset identification
- Service discovery
- Change detection
- Discovery history

---

4. Network Monitoring

VEXUS should monitor network behavior and infrastructure health.

Potential monitoring data:

- Device availability
- Latency
- Packet loss
- Bandwidth usage
- Connection activity
- Service availability
- Network changes

Monitoring should generate structured events.

---

5. VEXUS Network Event Contract

All major subsystems should communicate through a consistent event model.

Example concept:

SOURCE
   ↓
EVENT
   ↓
NORMALIZATION
   ↓
VALIDATION
   ↓
STORAGE
   ↓
DETECTION
   ↓
CORRELATION
   ↓
INCIDENT

A network event should support:

event_id
event_type
event_source
timestamp

asset_id
source_asset_id
destination_asset_id

severity
confidence
risk_score

evidence
metadata

correlation_id
parent_event_id

is_simulated
data_quality_score

Do not create unrelated event formats for every subsystem unless absolutely necessary.

---

6. Detection Engine

Detection is responsible for identifying meaningful patterns from raw events.

Initial detection capabilities should focus on:

- Repeated authentication failures
- Unusual asset changes
- Service changes
- Unexpected network behavior
- Availability anomalies
- Suspicious activity patterns

Detection output should be structured.

EVENTS
   ↓
RULE / DETECTOR
   ↓
DETECTION RESULT
   ↓
ALERT

A detection is not automatically an incident.

---

7. Alert Management

Alerts represent security-relevant findings.

An alert should contain:

ID
Title
Severity
Status
Source
Affected assets
Evidence
Detection rule
Created timestamp
Updated timestamp

Suggested statuses:

NEW
ACKNOWLEDGED
INVESTIGATING
RESOLVED
DISMISSED

---

8. Incident Correlation

Multiple related alerts should be capable of forming an incident.

Example:

Authentication Failures
        +
Suspicious Connection
        +
Asset Configuration Change
        ↓
    INCIDENT

Incident management should support:

- Incident timeline
- Related events
- Related alerts
- Affected assets
- Risk score
- Investigation notes
- Status changes
- Assignment

---

9. Risk Intelligence

VEXUS should calculate risk using multiple signals rather than a single arbitrary number.

Possible factors:

Asset importance
Exposure
Detected anomalies
Security events
Open services
Historical incidents
Confidence
Data quality

Conceptually:

RISK = ASSET CONTEXT
     + EXPOSURE
     + THREAT SIGNALS
     + BEHAVIORAL ANOMALIES

Risk calculations must remain explainable.

The system should be able to answer:

«Why does this asset have this risk score?»

---

10. Network Topology

VEXUS should visualize the discovered network.

Possible entities:

- Devices
- Networks
- Connections
- Services
- Gateways

Example:

Internet
    │
    ▼
Gateway
    │
 ┌──┴───────────────┐
 ▼                  ▼
Server           Workstation
 │                  │
 ▼                  ▼
Service           Service

Topology should be generated from actual discovered information where possible.

Do not make the topology purely decorative.

---

11. Authorized Device Management

Important Principle

VEXUS device management is for devices and infrastructure that the user owns or is explicitly authorized to administer.

The architecture must support administrative control without turning the platform into an unrestricted remote-control system.

The recommended architecture is:

VEXUS ADMIN PANEL
        │
        ▼
AUTHORIZATION CHECK
        │
        ▼
ACTION POLICY ENGINE
        │
        ▼
AUTHORIZED DEVICE / MANAGEMENT AGENT
        │
        ▼
DEVICE ACTION
        │
        ▼
AUDIT EVENT

Do not allow a frontend button to directly execute arbitrary commands on a network device.

Every management action should pass through:

1. Authentication
2. Permission checks
3. Device authorization
4. Action validation
5. Audit logging

Possible authorized actions may include:

- Device status checks
- Inventory synchronization
- Approved service management
- Agent communication
- Configuration synchronization
- Controlled reboot workflows
- Network isolation where supported and explicitly authorized

Dangerous or irreversible operations should require additional confirmation and appropriate permissions.

---

12. Device Management Agent Architecture

Directly trying to control every possible operating system through random remote shell commands is not a scalable architecture.

Instead, VEXUS should eventually support an optional management agent.

Concept:

┌─────────────────┐
│     VEXUS       │
│   Control API   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Management      │
│ Agent Protocol  │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
DEVICE A    DEVICE B

An agent should:

- Authenticate with VEXUS
- Identify the managed device
- Report approved telemetry
- Receive authorized tasks
- Validate tasks
- Report execution results

Agents must not silently execute arbitrary instructions.

---

13. AI Investigation Assistant

The AI subsystem should assist the user with understanding VEXUS data.

Example capabilities:

- Explain an alert
- Summarize an incident
- Explain a risk score
- Describe suspicious patterns
- Suggest investigation steps
- Summarize network changes

The AI should operate on structured platform data.

Preferred flow:

USER QUESTION
      ↓
PERMISSION CHECK
      ↓
RETRIEVE RELEVANT VEXUS DATA
      ↓
AI ANALYSIS
      ↓
EXPLAINABLE RESPONSE

Do not give the AI unrestricted direct access to infrastructure administration.

---

14. Simulation Mode

Simulation allows VEXUS to demonstrate features without requiring a live network.

Every simulated record must remain identifiable.

Example:

{
  "is_simulated": true,
  "event_source": "simulation"
}

Simulation data must never be mixed silently with production data.

The user should always know when data is simulated.

---

15. Health Monitoring

VEXUS should monitor itself.

Components may include:

Backend API
Database
Redis
Workers
Discovery integrations
Monitoring agents
External integrations

Health statuses:

HEALTHY
DEGRADED
UNHEALTHY
UNKNOWN

---

Frontend Vision

The frontend should feel like a serious security and infrastructure platform.

Primary areas should include:

Dashboard
Assets
Network
Topology
Events
Alerts
Incidents
Risk
Device Management
AI Investigation
System Health
Settings

The dashboard should prioritize useful intelligence over decorative charts.

A user should quickly understand:

- Current network state
- High-risk assets
- Active alerts
- Active incidents
- Recent changes
- System health

---

Frontend Architecture Rules

Features should be grouped by domain.

Example:

features/
├── assets/
├── discovery/
├── topology/
├── alerts/
├── incidents/
├── risk/
└── device-management/

Avoid placing all application logic inside page components.

Preferred pattern:

Page
 ↓
Feature Component
 ↓
Hooks
 ↓
API Service
 ↓
Backend

---

API Rules

All API endpoints should be versioned.

Example:

/api/v1/assets
/api/v1/events
/api/v1/alerts
/api/v1/incidents

Use:

- Pydantic schemas
- Explicit request validation
- Explicit response models
- Authentication dependencies
- Permission checks

Avoid returning raw database models directly.

---

Database Rules

The database is for persistent application state.

Use it for:

- Users
- Roles
- Permissions
- Assets
- Events
- Alerts
- Incidents
- Audit logs
- Configuration
- Historical state

Database changes must use migrations.

Do not rely on manually creating production tables at application startup.

Development shortcuts should not silently become production architecture.

---

Audit Logging

Security-sensitive actions must create audit records.

Examples:

user.login
user.login_failed

asset.scan_started
asset.scan_completed

device.management_requested
device.management_completed

alert.status_changed

incident.created
incident.updated

settings.changed

Audit logs should record:

Who
What
When
Where applicable: target
Result
Relevant context

Sensitive values such as:

passwords
tokens
secrets
credentials
private keys

must never be stored in plain form inside audit details.

---

Security Requirements

VEXUS must follow secure defaults.

Required principles:

- Secrets outside source control
- Environment-based configuration
- Password hashing
- Token expiration
- Backend authorization
- Least privilege
- Input validation
- Audit logging
- Safe path handling
- No arbitrary command execution
- No unrestricted remote-control API
- Explicit authorization for network operations

Use ".env.example" for configuration documentation.

Never commit real secrets.

---

Development Roadmap

Note: this roadmap reflects the original planning snapshot. It has not
been kept in sync with actual progress — see
`docs/architecture/V2_ARCHITECTURE_AUDIT.md` for the current, dated,
verified status (tests run, endpoints checked live) of what's actually
implemented versus still open. Several items below marked `[ ]` are in
fact done and tested (e.g. asset CRUD, discovery, monitoring, alerts,
incidents, risk, AI); reconciling this checklist against the audit doc
is itself an open task, not something to infer from these boxes alone.

Phase 1 — Foundation

Foundation includes:

- [x] Project structure
- [x] Backend foundation
- [x] Frontend foundation
- [x] Authentication architecture
- [x] RBAC foundation
- [x] Audit logging foundation
- [x] Event model foundation
- [x] Simulation foundation
- [x] Health monitoring foundation

Before assuming these are fully complete, inspect and test the current implementation.

Existing code may require repair or refactoring.

---

Phase 2 — Network Intelligence

Stage 1: Asset System

- [ ] Complete asset model
- [ ] Asset CRUD
- [ ] Asset history
- [ ] Asset status tracking
- [ ] Asset search and filtering

Stage 2: Authorized Discovery

- [ ] Scan scope management
- [ ] Discovery service abstraction
- [ ] Discovery integration
- [ ] Result normalization
- [ ] New asset detection
- [ ] Changed asset detection

Stage 3: Network Topology

- [ ] Network graph model
- [ ] Device relationships
- [ ] Connection visualization
- [ ] Topology API
- [ ] Interactive frontend visualization

---

Phase 3 — Monitoring and Detection

- [ ] Monitoring pipeline
- [ ] Event ingestion
- [ ] Event normalization
- [ ] Detection rules
- [ ] Alert generation
- [ ] Alert management

---

Phase 4 — Intelligence and Investigation

- [ ] Event correlation
- [ ] Incident creation
- [ ] Incident timelines
- [ ] Risk engine
- [ ] Investigation workflows
- [ ] AI-assisted explanations

---

Phase 5 — Authorized Infrastructure Management

- [ ] Device management architecture
- [ ] Agent protocol
- [ ] Managed-device registration
- [ ] Action policy system
- [ ] Command/task approval model
- [ ] Execution result reporting
- [ ] Comprehensive audit trails

---

Testing Requirements

Every major domain should have tests.

Backend

Test:

- Authentication
- Permissions
- API validation
- Asset logic
- Discovery normalization
- Event processing
- Detection
- Incident correlation

Frontend

Test:

- Critical navigation
- Authentication flow
- Permission-based UI
- API integration
- Error states

Integration

Test complete flows.

Example:

Authorized discovery
        ↓
Asset discovered
        ↓
Asset stored
        ↓
Event generated
        ↓
Detection evaluated
        ↓
Alert created
        ↓
Incident correlated

---

Code Quality Rules

Do not:

- Write massive single-purpose files
- Duplicate database queries
- Hardcode production secrets
- Hardcode fake data into real services
- Create unnecessary abstractions
- Mix frontend and backend responsibilities
- Bypass permission checks
- Silently ignore failures

Do:

- Use type hints
- Validate inputs
- Handle expected errors
- Log important failures
- Write focused services
- Reuse existing abstractions
- Add tests for important behavior
- Keep modules understandable

---

Definition of Done

A feature is not complete because:

- The file exists
- The endpoint was written
- The frontend button appears
- The code looks correct

A feature is complete when:

Implementation exists
        +
Relevant tests pass
        +
Frontend/backend integration works
        +
Errors are handled
        +
Permissions are enforced
        +
Documentation is updated

---

Copilot Development Instructions

When continuing VEXUS development:

1. Read this README.
2. Inspect the current codebase.
3. Identify the current development state.
4. Identify broken or incomplete features related to the requested task.
5. Do not rewrite working systems unnecessarily.
6. Build incrementally.
7. Run tests.
8. Fix discovered errors.
9. Do not claim implementation success without verification.
10. Explain what changed after completing a meaningful development phase.

When requirements conflict with existing code:

Preserve the architectural goal
over
blindly preserving old implementation details.

But do not destroy working functionality without a clear replacement.

---

Immediate Next Objective

Begin VEXUS v2 with a complete architecture audit.

Before adding large new features:

1. Inspect the entire existing codebase.
2. Map the current backend structure.
3. Map the frontend structure.
4. Identify missing imports and broken dependencies.
5. Check database configuration.
6. Check authentication flow.
7. Check API routes.
8. Check frontend-to-backend communication.
9. Run the application.
10. Run available tests.
11. Document the actual current state.

Then proceed with the first VEXUS v2 implementation milestone:

Asset Intelligence and Authorized Network Discovery

The goal is to establish the reliable foundation that all later VEXUS intelligence depends on.

---

Final Architectural Principle

VEXUS should not become a collection of random security features.

Every capability should strengthen the same intelligence pipeline.

DISCOVER
    ↓
IDENTIFY
    ↓
MONITOR
    ↓
NORMALIZE
    ↓
DETECT
    ↓
CORRELATE
    ↓
ASSESS RISK
    ↓
INVESTIGATE
    ↓
EXPLAIN
    ↓
RESPOND
    ↓
MANAGE AUTHORIZED INFRASTRUCTURE

VEXUS v2 is the platform where these systems connect.