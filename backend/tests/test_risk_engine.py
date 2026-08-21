from datetime import datetime, timezone

from app.alerts.models import Alert, AlertStatus
from app.assets.models import Asset, AssetCriticality, AssetTrustStatus
from app.events.models import EventSeverity
from app.health.models import WorkerHeartbeat
from app.risk.models import RiskLevel
from app.risk.service import RiskEngine


def _seed_asset(db_session, criticality=AssetCriticality.LOW, trust_status=AssetTrustStatus.UNKNOWN):
    now = datetime.now(timezone.utc)
    asset = Asset(
        ip_address="10.0.0.30",
        criticality=criticality,
        trust_status=trust_status,
        first_seen=now,
        last_seen=now,
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def _seed_alert(db_session, asset_id, severity=EventSeverity.HIGH, confidence=1.0, status=AlertStatus.NEW, dedup_suffix=""):
    now = datetime.now(timezone.utc)
    alert = Alert(
        rule_key="test_rule",
        asset_id=asset_id,
        severity=severity,
        confidence=confidence,
        status=status,
        description="test",
        evidence="[]",
        dedup_key=f"test_rule:{asset_id}{dedup_suffix}",
        occurrence_count=1,
        first_seen=now,
        last_seen=now,
        suppressed=False,
        is_synthetic=False,
    )
    db_session.add(alert)
    db_session.commit()
    return alert


def test_low_criticality_unknown_trust_no_alerts_is_low_risk(db_session):
    asset = _seed_asset(db_session, criticality=AssetCriticality.LOW, trust_status=AssetTrustStatus.UNKNOWN)
    engine = RiskEngine(db_session)

    risk_score = engine.compute_for_asset(asset)

    assert risk_score.score == 10  # trust=unknown (+10) only, criticality=low (+0)
    assert risk_score.risk_level == RiskLevel.LOW


def test_critical_untrusted_asset_scores_high(db_session):
    asset = _seed_asset(db_session, criticality=AssetCriticality.CRITICAL, trust_status=AssetTrustStatus.UNTRUSTED)
    engine = RiskEngine(db_session)

    risk_score = engine.compute_for_asset(asset)

    assert risk_score.score == 50  # 25 (critical) + 25 (untrusted)
    assert risk_score.risk_level == RiskLevel.HIGH


def test_trusted_low_criticality_asset_is_low_risk(db_session):
    asset = _seed_asset(db_session, criticality=AssetCriticality.LOW, trust_status=AssetTrustStatus.TRUSTED)
    engine = RiskEngine(db_session)

    risk_score = engine.compute_for_asset(asset)

    assert risk_score.score == 0
    assert risk_score.risk_level == RiskLevel.LOW


def test_active_alert_contributes_to_score(db_session):
    asset = _seed_asset(db_session, criticality=AssetCriticality.LOW, trust_status=AssetTrustStatus.TRUSTED)
    _seed_alert(db_session, asset.id, severity=EventSeverity.HIGH, confidence=1.0)
    engine = RiskEngine(db_session)

    risk_score = engine.compute_for_asset(asset)

    assert risk_score.score == 14  # HIGH weight (14) * confidence (1.0)


def test_alert_confidence_scales_contribution(db_session):
    asset = _seed_asset(db_session, criticality=AssetCriticality.LOW, trust_status=AssetTrustStatus.TRUSTED)
    _seed_alert(db_session, asset.id, severity=EventSeverity.HIGH, confidence=0.5)
    engine = RiskEngine(db_session)

    risk_score = engine.compute_for_asset(asset)

    assert risk_score.score == 7.0  # 14 * 0.5


def test_resolved_alert_does_not_contribute(db_session):
    asset = _seed_asset(db_session, criticality=AssetCriticality.LOW, trust_status=AssetTrustStatus.TRUSTED)
    _seed_alert(db_session, asset.id, severity=EventSeverity.CRITICAL, confidence=1.0, status=AlertStatus.RESOLVED)
    engine = RiskEngine(db_session)

    risk_score = engine.compute_for_asset(asset)

    assert risk_score.score == 0  # resolved alerts are not "active"


def test_alert_contribution_is_capped(db_session):
    asset = _seed_asset(db_session, criticality=AssetCriticality.LOW, trust_status=AssetTrustStatus.TRUSTED)
    for i in range(5):
        _seed_alert(db_session, asset.id, severity=EventSeverity.CRITICAL, confidence=1.0, dedup_suffix=f":{i}")

    engine = RiskEngine(db_session)
    risk_score = engine.compute_for_asset(asset)

    assert risk_score.score == 40  # capped, not 100 (5 * 20)


def test_factors_are_persisted_and_explain_the_score(db_session):
    asset = _seed_asset(db_session, criticality=AssetCriticality.HIGH, trust_status=AssetTrustStatus.UNKNOWN)
    engine = RiskEngine(db_session)

    risk_score = engine.compute_for_asset(asset)
    factors = engine.repo.get_factors(risk_score.id)

    factor_keys = {f.factor_key for f in factors}
    assert "criticality" in factor_keys
    assert "trust_status" in factor_keys
    assert sum(f.points for f in factors) == risk_score.score


def test_asset_risk_score_field_is_kept_in_sync(db_session):
    asset = _seed_asset(db_session, criticality=AssetCriticality.CRITICAL, trust_status=AssetTrustStatus.UNTRUSTED)
    engine = RiskEngine(db_session)

    engine.compute_for_asset(asset)

    db_session.refresh(asset)
    assert asset.risk_score == 50


def test_recompute_all_scores_every_asset(db_session):
    _seed_asset(db_session, criticality=AssetCriticality.LOW)
    _seed_asset(db_session, criticality=AssetCriticality.HIGH)
    engine = RiskEngine(db_session)

    summary = engine.recompute_all()

    assert summary.assets_scored == 2


def test_recompute_flags_stale_detection_data(db_session):
    # no WorkerHeartbeat("detection") row exists at all -> stale
    engine = RiskEngine(db_session)
    summary = engine.recompute_all()

    assert summary.detection_data_stale is True

    from app.common.models import DataQualityWarning

    warnings = db_session.query(DataQualityWarning).filter_by(subject_type="risk").all()
    assert len(warnings) == 1


def test_recompute_does_not_flag_fresh_detection_data(db_session):
    now = datetime.now(timezone.utc)
    db_session.add(WorkerHeartbeat(worker_name="detection", last_success_at=now, status="ok", detail=""))
    db_session.commit()

    engine = RiskEngine(db_session)
    summary = engine.recompute_all()

    assert summary.detection_data_stale is False


def test_new_risk_score_history_accumulates(db_session):
    asset = _seed_asset(db_session)
    engine = RiskEngine(db_session)

    engine.compute_for_asset(asset)
    engine.compute_for_asset(asset)

    history = engine.repo.get_history_for_asset(asset.id)
    assert len(history) == 2
