from datetime import datetime, timezone

import pytest

from app.assets.models import Asset, AssetTrustStatus
from app.events.models import EventSeverity, EventSource, NetworkEvent
from app.events.schemas import EventIngestRequest
from app.events.service import EventIngestionError, EventIngestionService


def _seed_asset(db_session, ip_address="10.0.0.50"):
    now = datetime.now(timezone.utc)
    asset = Asset(ip_address=ip_address, trust_status=AssetTrustStatus.UNKNOWN, first_seen=now, last_seen=now)
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def test_ingest_resolves_asset_by_ip(db_session):
    asset = _seed_asset(db_session)
    request = EventIngestRequest(
        event_type="SYSLOG_AUTH_FAILURE",
        event_source=EventSource.SYSLOG,
        ip_address=asset.ip_address,
    )

    results = EventIngestionService(db_session).ingest_batch([request], actor=None)
    event, matched = results[0]

    assert matched is True
    assert event.asset_id == asset.id
    assert event.event_source == EventSource.SYSLOG


def test_ingest_with_unmatched_ip_preserves_ip_in_metadata(db_session):
    request = EventIngestRequest(
        event_type="THREAT_INTEL_MATCH",
        event_source=EventSource.THREAT_INTEL,
        ip_address="203.0.113.9",
    )

    results = EventIngestionService(db_session).ingest_batch([request], actor=None)
    event, matched = results[0]

    assert matched is False
    assert event.asset_id is None
    assert "203.0.113.9" in event.event_metadata


def test_ingest_never_trusts_client_supplied_synthetic_or_processed_flags(db_session):
    """The schema doesn't even expose is_synthetic/processed_by_detection
    as settable fields, but this locks in the guarantee at the service
    level too: every ingested event is real, unprocessed data."""
    request = EventIngestRequest(event_type="MANUAL_NOTE", event_source=EventSource.MANUAL)
    results = EventIngestionService(db_session).ingest_batch([request], actor=None)
    event, _ = results[0]

    assert event.is_synthetic is False
    assert event.processed_by_detection is False


def test_ingest_rejects_disallowed_event_source():
    with pytest.raises(ValueError):
        EventIngestRequest(event_type="FAKE_DISCOVERY", event_source=EventSource.DISCOVERY)


def test_ingest_rejects_simulation_source_spoofing():
    with pytest.raises(ValueError):
        EventIngestRequest(event_type="FAKE_SIM", event_source=EventSource.SIMULATION)


def test_ingest_rejects_oversized_evidence(db_session):
    request = EventIngestRequest(
        event_type="SYSLOG_BULK",
        event_source=EventSource.SYSLOG,
        evidence=["x" * 5000],
    )
    with pytest.raises(EventIngestionError, match="evidence exceeds"):
        EventIngestionService(db_session).ingest_batch([request], actor=None)


def test_ingest_rejects_unknown_asset_id(db_session):
    request = EventIngestRequest(
        event_type="SYSLOG_EVENT",
        event_source=EventSource.SYSLOG,
        asset_id="does-not-exist",
    )
    with pytest.raises(EventIngestionError, match="does not exist"):
        EventIngestionService(db_session).ingest_batch([request], actor=None)


def test_confidence_out_of_range_is_rejected_by_schema():
    with pytest.raises(ValueError):
        EventIngestRequest(event_type="X", event_source=EventSource.SYSLOG, confidence=1.5)


def test_ingested_event_flows_into_detection(db_session):
    """The whole point of the ingestion boundary: an externally-sourced
    event must enter the exact same detection pipeline as an internally
    generated one, with no separate ingestion-specific detection path."""
    from app.detection.service import DetectionEngine

    asset = _seed_asset(db_session)
    request = EventIngestRequest(
        event_type="AVAILABILITY_ANOMALY",
        event_source=EventSource.SYSLOG,
        ip_address=asset.ip_address,
        severity=EventSeverity.MEDIUM,
    )
    EventIngestionService(db_session).ingest_batch([request], actor=None)

    summary = DetectionEngine(db_session).run(actor=None)

    assert summary.alerts_created + summary.alerts_updated >= 1
    event = db_session.query(NetworkEvent).filter_by(event_type="AVAILABILITY_ANOMALY").first()
    assert event.processed_by_detection is True
