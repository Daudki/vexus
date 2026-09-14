from datetime import datetime, timezone
import json

import pytest

from app.events.models import EventSource, NetworkEvent
from app.threat_intel.models import Vulnerability
from app.threat_intel.provider import NVDProvider, ThreatIntelProviderError, VulnerabilityRecord
from app.threat_intel.repository import VulnerabilityRepository
from app.threat_intel.service import ThreatIntelService


class FakeProvider:
    def __init__(self, record):
        self.record = record

    def fetch_cve(self, cve_id):
        assert cve_id == self.record.cve_id
        return self.record


def _record(cve_id="CVE-2026-12345", score=9.8):
    return VulnerabilityRecord(
        cve_id=cve_id,
        source="nvd",
        description="Example vulnerability",
        cvss_score=score,
        cvss_severity="CRITICAL",
        cvss_version="4.0",
        published_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
        last_modified_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
        cwe_ids=["CWE-79"],
        affected_cpes=["cpe:2.3:a:example:product:*:*:*:*:*:*:*:*"] ,
        references=["https://example.test/CVE-2026-12345"],
        # raw_data must vary with `score`, matching real NVD behavior:
        # the score is always extracted from this same payload (see
        # NVDProvider._first_metric), so the two can never actually
        # diverge in production the way a fixture easily could by
        # accident. ThreatIntelService detects "did this CVE change"
        # by comparing raw_data, so a fixture that changes score
        # without changing raw_data silently fails to exercise the
        # "updated" path at all.
        raw_data={"id": cve_id, "description": "Example vulnerability", "score": score},
        is_rejected=False,
    )


def test_sync_creates_vulnerability_and_threat_event(db_session):
    vulnerability, created, updated, event_id = ThreatIntelService(db_session, FakeProvider(_record())).sync_cve("CVE-2026-12345")

    assert created is True
    assert updated is False
    assert event_id is not None
    assert vulnerability.cve_id == "CVE-2026-12345"
    assert db_session.query(Vulnerability).count() == 1
    event = db_session.get(NetworkEvent, event_id)
    assert event.event_source == EventSource.THREAT_INTEL
    assert event.processed_by_detection is False


def test_sync_same_payload_is_idempotent(db_session):
    service = ThreatIntelService(db_session, FakeProvider(_record()))
    _, created1, updated1, event1 = service.sync_cve("CVE-2026-12345")
    _, created2, updated2, event2 = service.sync_cve("CVE-2026-12345")

    assert (created1, updated1, event1 is not None) == (True, False, True)
    assert (created2, updated2, event2) == (False, False, None)
    assert db_session.query(Vulnerability).count() == 1


def test_sync_changed_payload_updates_and_emits_event(db_session):
    first = _record()
    second = _record(score=10.0)
    service = ThreatIntelService(db_session, FakeProvider(first))
    service.sync_cve(first.cve_id)
    service.provider = FakeProvider(second)
    _, created, updated, event_id = service.sync_cve(second.cve_id)

    assert created is False
    assert updated is True
    assert event_id is not None
    assert db_session.query(Vulnerability).count() == 1


def test_repository_lists_vulnerabilities(db_session):
    service = ThreatIntelService(db_session, FakeProvider(_record()))
    service.sync_cve("CVE-2026-12345")
    rows, total = VulnerabilityRepository(db_session).list(search="12345", severity="CRITICAL")
    assert total == 1
    assert rows[0].cve_id == "CVE-2026-12345"


def test_nvd_provider_parses_normalized_cve_payload(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({
                "vulnerabilities": [{"cve": {
                    "id": "CVE-2026-12345",
                    "published": "2026-09-01T00:00:00.000Z",
                    "lastModified": "2026-09-02T00:00:00.000Z",
                    "descriptions": [{"lang": "en", "value": "Example vulnerability"}],
                    "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": 8.8, "baseSeverity": "HIGH"}}]},
                    "weaknesses": [{"description": [{"lang": "en", "value": "CWE-79"}]}],
                    "configurations": [{"nodes": [{"cpeMatch": [{"criteria": "cpe:2.3:a:example:product:*:*:*:*:*:*:*:*"}]}]}],
                    "references": [{"url": "https://example.test/advisory"}],
                    "vulnStatus": "Analyzed",
                }}]
            }).encode()

    monkeypatch.setattr("app.threat_intel.provider.urlopen", lambda *args, **kwargs: Response())
    record = NVDProvider("https://services.nvd.nist.gov/rest/json").fetch_cve("cve-2026-12345")

    assert record.cve_id == "CVE-2026-12345"
    assert record.cvss_score == 8.8
    assert record.cvss_severity == "HIGH"
    assert record.cwe_ids == ["CWE-79"]
    assert record.affected_cpes == ["cpe:2.3:a:example:product:*:*:*:*:*:*:*:*"]
    assert record.references == ["https://example.test/advisory"]


def test_nvd_provider_rejects_invalid_cve_id():
    provider = NVDProvider("https://example.test")
    with pytest.raises(ThreatIntelProviderError, match="CVE ID"):
        provider.fetch_cve("12345")


def test_nvd_provider_rejects_cve_id_with_trailing_garbage():
    """Only checking startswith('CVE-') would let something like
    'CVE-2026-1234; DROP TABLE' through the provider layer -- not a SQL
    injection risk (the ORM parameterizes it), but it could still exceed
    the cve_id column's length or send a malformed query to NVD instead
    of failing cleanly here."""
    provider = NVDProvider("https://example.test")
    with pytest.raises(ThreatIntelProviderError, match="CVE ID"):
        provider.fetch_cve("CVE-2026-1234-extra-stuff")


def test_nvd_provider_handles_non_numeric_cvss_score_gracefully(monkeypatch):
    """A malformed provider response must not turn into an unhandled
    500 for the whole sync -- degrade to a null score instead."""
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({
                "vulnerabilities": [{"cve": {
                    "id": "CVE-2026-99999",
                    "descriptions": [{"lang": "en", "value": "x"}],
                    "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": "not-a-number", "baseSeverity": "HIGH"}}]},
                    "vulnStatus": "Analyzed",
                }}]
            }).encode()

    monkeypatch.setattr("app.threat_intel.provider.urlopen", lambda *args, **kwargs: Response())
    record = NVDProvider("https://services.nvd.nist.gov/rest/json").fetch_cve("CVE-2026-99999")
    assert record.cvss_score is None


def test_repository_count_matches_actual_rows_not_full_scan(db_session):
    """Regression test: a previous version computed the total by loading
    every matching row into memory (`len(list(...))`), which would be a
    real resource-exhaustion vector against NVD's real CVE volume. This
    just confirms the count is still correct after switching to a
    SQL-side COUNT."""
    for i in range(5):
        record = _record(cve_id=f"CVE-2026-{10000+i}")
        VulnerabilityRepository(db_session).upsert(record)
    db_session.commit()

    rows, total = VulnerabilityRepository(db_session).list(limit=2, offset=0)
    assert total == 5
    assert len(rows) == 2


def test_oversized_raw_data_is_truncated_not_stored_in_full(db_session):
    huge_payload = {"id": "CVE-2026-77777", "blob": "x" * 300_000}
    record = _record(cve_id="CVE-2026-77777")
    record = VulnerabilityRecord(**{**record.__dict__, "raw_data": huge_payload})

    vulnerability, created, _ = VulnerabilityRepository(db_session).upsert(record)
    db_session.commit()

    assert created is True
    assert len(vulnerability.raw_data) < 300_000
    assert "_truncated" in vulnerability.raw_data
