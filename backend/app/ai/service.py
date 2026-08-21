"""
AI application service.

Every method here builds a deliberately minimal context (only the
fields already surfaced elsewhere in the platform — never a raw DB
dump) and logs the query + response via AIQueryLog, regardless of
whether the call succeeded. If the provider raises AIProviderError,
that's captured as a recommendation-only, zero-confidence response —
never silently swallowed, and never backfilled with a fabricated
answer.
"""
import json

from sqlalchemy.orm import Session

from app.ai.models import AIQueryLog
from app.ai.provider import AIProvider, AIProviderError, AIResponse
from app.alerts.models import Alert
from app.assets.models import Asset
from app.config.settings import get_settings
from app.events.models import NetworkEvent
from app.incidents.models import Incident
from app.incidents.service import IncidentService
from app.users.models import User

SYSTEM_PROMPT = (
    "You are the VEXUS security assistant. You explain and summarize security data for a human "
    "analyst. You must operate ONLY on the structured context provided in the user message — you "
    "have no access to the network, no memory of other conversations, and no knowledge about this "
    "specific organization beyond what's given. Never invent a detail that isn't in the context."
)


class AIServiceError(Exception):
    pass


class AIService:
    def __init__(self, db: Session, provider: AIProvider):
        self.db = db
        self.provider = provider

    def _run(self, *, query_type: str, target_type: str, target_id: str, question: str, user_prompt: str, actor: User) -> AIQueryLog:
        try:
            response = self.provider.generate(SYSTEM_PROMPT, user_prompt)
        except AIProviderError as exc:
            response = AIResponse(recommendations=[f"AI request failed: {exc}"], confidence=0.0)

        settings = get_settings()
        entry = AIQueryLog(
            query_type=query_type,
            target_type=target_type,
            target_id=target_id,
            question=question,
            observed_facts=json.dumps(response.observed_facts),
            inferences=json.dumps(response.inferences),
            hypotheses=json.dumps(response.hypotheses),
            recommendations=json.dumps(response.recommendations),
            confidence=response.confidence,
            actor_user_id=actor.id if actor else None,
            provider=settings.AI_PROVIDER,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def explain_alert(self, alert_id: str, actor: User) -> AIQueryLog:
        alert = self.db.get(Alert, alert_id)
        if alert is None:
            raise AIServiceError("Alert not found.")

        asset = self.db.get(Asset, alert.asset_id) if alert.asset_id else None
        try:
            event_ids = json.loads(alert.evidence or "[]")
        except (json.JSONDecodeError, TypeError):
            event_ids = []
        events = self.db.query(NetworkEvent).filter(NetworkEvent.id.in_(event_ids)).all() if event_ids else []

        lines = [
            f"Alert rule: {alert.rule_key}",
            f"Severity: {alert.severity.value}",
            f"Confidence: {alert.confidence:.0%}",
            f"Status: {alert.status.value}",
            f"Occurrences: {alert.occurrence_count}",
            f"Description: {alert.description}",
        ]
        if asset:
            lines += [
                f"Affected asset: {asset.hostname or asset.ip_address or asset.id}",
                f"Asset criticality: {asset.criticality.value}",
                f"Asset trust status: {asset.trust_status.value}",
            ]
        for event in events:
            lines.append(f"Evidence event: {event.event_type} at {event.timestamp.isoformat()} — {event.description}")

        user_prompt = "Explain this security alert to an analyst.\n\nContext:\n" + "\n".join(lines)
        return self._run(
            query_type="explain_alert", target_type="alert", target_id=alert_id, question="", user_prompt=user_prompt, actor=actor
        )

    def summarize_incident(self, incident_id: str, actor: User) -> AIQueryLog:
        incident = self.db.get(Incident, incident_id)
        if incident is None:
            raise AIServiceError("Incident not found.")

        timeline = IncidentService(self.db).get_timeline(incident)

        lines = [
            f"Incident: {incident.title}",
            f"Description: {incident.description}",
            f"Severity: {incident.severity.value}",
            f"Confidence: {incident.confidence:.0%}",
            f"Status: {incident.status.value}",
        ]
        for entry in timeline[:30]:  # bound context size
            lines.append(f"[{entry.kind}] {entry.timestamp.isoformat()}: {entry.summary}")

        user_prompt = "Summarize this security incident for a handoff to another analyst.\n\nContext:\n" + "\n".join(lines)
        return self._run(
            query_type="summarize_incident",
            target_type="incident",
            target_id=incident_id,
            question="",
            user_prompt=user_prompt,
            actor=actor,
        )

    def ask(self, context_type: str, context_id: str, question: str, actor: User) -> AIQueryLog:
        if context_type == "alert":
            alert = self.db.get(Alert, context_id)
            if alert is None:
                raise AIServiceError("Alert not found.")
            lines = [f"Alert: {alert.rule_key}, severity {alert.severity.value}, confidence {alert.confidence:.0%}. {alert.description}"]
        elif context_type == "incident":
            incident = self.db.get(Incident, context_id)
            if incident is None:
                raise AIServiceError("Incident not found.")
            lines = [f"Incident: {incident.title} — {incident.description}. Status: {incident.status.value}."]
        elif context_type == "asset":
            asset = self.db.get(Asset, context_id)
            if asset is None:
                raise AIServiceError("Asset not found.")
            lines = [
                f"Asset: {asset.hostname or asset.ip_address}, criticality {asset.criticality.value}, "
                f"trust status {asset.trust_status.value}, risk score {asset.risk_score:.0f}."
            ]
        else:
            raise AIServiceError(f"Unknown context_type '{context_type}'. Must be alert, incident, or asset.")

        user_prompt = f"{question}\n\nContext:\n" + "\n".join(lines)
        return self._run(
            query_type="ask", target_type=context_type, target_id=context_id, question=question, user_prompt=user_prompt, actor=actor
        )
