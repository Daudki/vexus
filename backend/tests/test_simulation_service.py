from app.alerts.models import Alert
from app.assets.models import Asset
from app.events.models import NetworkEvent
from app.incidents.models import Incident
from app.incidents.service import IncidentError, IncidentService
from app.simulation.service import SimulationService


def test_run_scenario_creates_synthetic_assets_and_events(db_session):
    result = SimulationService(db_session).run_scenario(actor=None)

    assert result.assets_created == 2
    assert result.events_created == 2

    assets = db_session.query(Asset).filter_by(is_synthetic=True).all()
    events = db_session.query(NetworkEvent).filter_by(is_synthetic=True).all()
    assert len(assets) == 2
    assert len(events) == 2
    assert all(a.hostname.startswith("SIM-") for a in assets)
    assert all(a.ip_address.startswith("198.51.100.") for a in assets)


def test_run_scenario_produces_alerts_marked_synthetic(db_session):
    result = SimulationService(db_session).run_scenario(actor=None)

    assert result.alerts_created >= 1
    alerts = db_session.query(Alert).filter_by(is_synthetic=True).all()
    assert len(alerts) >= 1
    assert all(a.is_synthetic for a in alerts)


def test_run_scenario_does_not_affect_real_data(db_session):
    """A previously-existing real asset/event must be completely
    untouched by running a simulation scenario."""
    from datetime import datetime, timezone
    from app.assets.models import AssetStatus, AssetTrustStatus

    real_asset = Asset(
        hostname="real-host",
        ip_address="10.0.0.5",
        status=AssetStatus.ONLINE,
        trust_status=AssetTrustStatus.UNKNOWN,
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
        is_synthetic=False,
    )
    db_session.add(real_asset)
    db_session.commit()

    SimulationService(db_session).run_scenario(actor=None)

    db_session.refresh(real_asset)
    assert real_asset.is_synthetic is False
    assert db_session.query(Asset).filter_by(is_synthetic=False).count() == 1


def test_reset_deletes_all_synthetic_data(db_session):
    SimulationService(db_session).run_scenario(actor=None)
    result = SimulationService(db_session).reset(actor=None)

    assert result.assets_deleted == 2
    assert result.events_deleted == 2
    assert result.alerts_deleted >= 1

    assert db_session.query(Asset).filter_by(is_synthetic=True).count() == 0
    assert db_session.query(NetworkEvent).filter_by(is_synthetic=True).count() == 0
    assert db_session.query(Alert).filter_by(is_synthetic=True).count() == 0


def test_reset_also_deletes_synthetic_incident_and_its_links(db_session):
    from app.users.models import Role, RoleName, User
    from app.core.security import hash_password

    SimulationService(db_session).run_scenario(actor=None)
    role = db_session.query(Role).filter_by(name=RoleName.ADMIN).first()
    admin = User(username="admin1", email="admin1@vexus.local", password_hash=hash_password("x"), role_id=role.id)
    db_session.add(admin)
    db_session.commit()

    synthetic_alert = db_session.query(Alert).filter_by(is_synthetic=True).first()
    incident = IncidentService(db_session).create_incident(
        title="Simulated incident",
        description="test",
        alert_ids=[synthetic_alert.id],
        asset_ids=[],
        actor=admin,
    )
    assert incident.is_synthetic is True

    result = SimulationService(db_session).reset(actor=None)
    assert result.incidents_deleted == 1
    assert db_session.query(Incident).filter_by(is_synthetic=True).count() == 0


def test_reset_leaves_real_incidents_untouched(db_session):
    from datetime import datetime, timezone
    from app.assets.models import AssetStatus, AssetTrustStatus
    from app.users.models import Role, RoleName, User
    from app.core.security import hash_password

    real_asset = Asset(
        hostname="real-host",
        ip_address="10.0.0.5",
        status=AssetStatus.ONLINE,
        trust_status=AssetTrustStatus.UNKNOWN,
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
        is_synthetic=False,
    )
    db_session.add(real_asset)
    role = db_session.query(Role).filter_by(name=RoleName.ADMIN).first()
    admin = User(username="admin1", email="admin1@vexus.local", password_hash=hash_password("x"), role_id=role.id)
    db_session.add(admin)
    db_session.commit()

    real_incident = IncidentService(db_session).create_incident(
        title="Real incident", description="test", alert_ids=[], asset_ids=[real_asset.id], actor=admin,
    )

    SimulationService(db_session).run_scenario(actor=None)
    SimulationService(db_session).reset(actor=None)

    db_session.refresh(real_incident)
    assert db_session.query(Incident).filter_by(id=real_incident.id).count() == 1


def test_status_reports_zero_before_any_scenario_runs(db_session):
    status = SimulationService(db_session).status()
    assert status.active is False
    assert status.assets == 0 == status.events == status.alerts == status.incidents


def test_status_reflects_active_scenario(db_session):
    SimulationService(db_session).run_scenario(actor=None)
    status = SimulationService(db_session).status()
    assert status.active is True
    assert status.assets == 2
    assert status.events == 2


def test_cannot_create_incident_mixing_real_and_synthetic_alerts(db_session):
    from datetime import datetime, timezone
    from app.assets.models import AssetStatus, AssetTrustStatus
    from app.users.models import Role, RoleName, User
    from app.core.security import hash_password
    from app.alerts.models import AlertStatus
    from app.events.models import EventSeverity

    SimulationService(db_session).run_scenario(actor=None)
    synthetic_alert = db_session.query(Alert).filter_by(is_synthetic=True).first()

    real_asset = Asset(
        hostname="real-host",
        ip_address="10.0.0.5",
        status=AssetStatus.ONLINE,
        trust_status=AssetTrustStatus.UNKNOWN,
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
        is_synthetic=False,
    )
    db_session.add(real_asset)
    db_session.commit()

    real_alert = Alert(
        rule_key="new_device_detection",
        asset_id=real_asset.id,
        severity=EventSeverity.MEDIUM,
        confidence=0.9,
        status=AlertStatus.NEW,
        description="real",
        evidence="[]",
        dedup_key="real-dedup-key",
        occurrence_count=1,
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
        is_synthetic=False,
    )
    db_session.add(real_alert)

    role = db_session.query(Role).filter_by(name=RoleName.ADMIN).first()
    admin = User(username="admin1", email="admin1@vexus.local", password_hash=hash_password("x"), role_id=role.id)
    db_session.add(admin)
    db_session.commit()

    import pytest
    with pytest.raises(IncidentError, match="mix of simulated and real"):
        IncidentService(db_session).create_incident(
            title="Mixed incident",
            description="test",
            alert_ids=[synthetic_alert.id, real_alert.id],
            asset_ids=[],
            actor=admin,
        )
