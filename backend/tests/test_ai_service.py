import json
from datetime import datetime, timezone

import pytest

from app.ai.provider import AIProviderError, AIResponse
from app.ai.service import AIService, AIServiceError
from app.alerts.models import Alert, AlertStatus
from app.assets.models import Asset, AssetTrustStatus
from app.core.security import hash_password
from app.events.models import EventSeverity, EventSource, NetworkEvent
from app.users.models import Role, RoleName, User


class FakeProvider:
    """Test-only stand-in for AIProvider — captures the prompt it was
    called with so tests can assert on what context was actually sent."""

    def __init__(self, response: AIResponse | None = None, raise_error: bool = False):
        self.response = response or AIResponse(
            observed_facts=["fact"], inferences=["inference"], hypotheses=["hypothesis"],
            recommendations=["recommendation"], confidence=0.75,
        )
        self.raise_error = raise_error
        self.last_system_prompt: str | None = None
        self.last_user_prompt: str | None = None

    def generate(self, system_prompt: str, user_prompt: str) -> AIResponse:
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        if self.raise_error:
            raise AIProviderError("simulated failure")
        return self.response


def _seed_user(db_session, username="analyst1"):
    role = db_session.query(Role).filter_by(name=RoleName.SECURITY_ANALYST).first()
    user = User(username=username, email=f"{username}@vexus.local", password_hash=hash_password("x"), role_id=role.id)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _seed_alert_with_event(db_session):
    now = datetime.now(timezone.utc)
    asset = Asset(ip_address="10.0.0.80", trust_status=AssetTrustStatus.UNKNOWN, first_seen=now, last_seen=now)
    db_session.add(asset)
    db_session.commit()

    event = NetworkEvent(
        event_type="NEW_DEVICE", event_source=EventSource.DISCOVERY, timestamp=now, asset_id=asset.id,
        severity=EventSeverity.MEDIUM, confidence=0.9, description="test event", evidence="[]", is_synthetic=False,
    )
    db_session.add(event)
    db_session.commit()

    alert = Alert(
        rule_key="new_device_detection", asset_id=asset.id, severity=EventSeverity.MEDIUM, confidence=0.9,
        status=AlertStatus.NEW, description="test alert", evidence=json.dumps([event.id]),
        dedup_key=f"new_device_detection:{asset.id}", occurrence_count=1, first_seen=now, last_seen=now,
        suppressed=False, is_synthetic=False,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    return alert, asset


def test_explain_alert_persists_structured_response(db_session):
    actor = _seed_user(db_session)
    alert, asset = _seed_alert_with_event(db_session)
    provider = FakeProvider()

    log = AIService(db_session, provider).explain_alert(alert.id, actor)

    assert log.query_type == "explain_alert"
    assert log.target_id == alert.id
    assert json.loads(log.observed_facts) == ["fact"]
    assert json.loads(log.inferences) == ["inference"]
    assert log.confidence == 0.75


def test_explain_alert_context_includes_asset_and_event_details(db_session):
    actor = _seed_user(db_session)
    alert, asset = _seed_alert_with_event(db_session)
    provider = FakeProvider()

    AIService(db_session, provider).explain_alert(alert.id, actor)

    assert asset.ip_address in provider.last_user_prompt
    assert "NEW_DEVICE" in provider.last_user_prompt
    assert "new_device_detection" in provider.last_user_prompt


def test_explain_nonexistent_alert_raises(db_session):
    actor = _seed_user(db_session)
    provider = FakeProvider()

    with pytest.raises(AIServiceError, match="Alert not found"):
        AIService(db_session, provider).explain_alert("does-not-exist", actor)


def test_provider_error_is_captured_not_raised(db_session):
    actor = _seed_user(db_session)
    alert, asset = _seed_alert_with_event(db_session)
    provider = FakeProvider(raise_error=True)

    log = AIService(db_session, provider).explain_alert(alert.id, actor)

    assert log.confidence == 0.0
    assert json.loads(log.observed_facts) == []  # never fabricated when the call failed
    assert "AI request failed" in json.loads(log.recommendations)[0]


def test_ask_with_unknown_context_type_raises(db_session):
    actor = _seed_user(db_session)
    provider = FakeProvider()

    with pytest.raises(AIServiceError, match="Unknown context_type"):
        AIService(db_session, provider).ask("not_a_real_type", "some-id", "question?", actor)


def test_ask_about_asset_includes_risk_score_in_context(db_session):
    actor = _seed_user(db_session)
    now = datetime.now(timezone.utc)
    asset = Asset(ip_address="10.0.0.81", trust_status=AssetTrustStatus.UNKNOWN, risk_score=42.0, first_seen=now, last_seen=now)
    db_session.add(asset)
    db_session.commit()

    provider = FakeProvider()
    log = AIService(db_session, provider).ask("asset", asset.id, "Why is this risky?", actor)

    assert "42" in provider.last_user_prompt
    assert log.question == "Why is this risky?"


def test_ai_query_is_logged_with_actor(db_session):
    actor = _seed_user(db_session, username="analyst_x")
    alert, asset = _seed_alert_with_event(db_session)
    provider = FakeProvider()

    log = AIService(db_session, provider).explain_alert(alert.id, actor)

    assert log.actor_user_id == actor.id
