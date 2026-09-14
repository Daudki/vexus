from unittest.mock import patch

from app.core.security import hash_password
from app.threat_intel.provider import VulnerabilityRecord
from app.users.models import Role, RoleName, User
from datetime import datetime, timezone


def _create_and_login(client, db_session, username, role_name, password="Password123!"):
    role = db_session.query(Role).filter_by(name=role_name).first()
    user = User(
        username=username,
        email=f"{username}@vexus.local",
        password_hash=hash_password(password),
        role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()

    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.json()["access_token"]


def _fake_record():
    return VulnerabilityRecord(
        cve_id="CVE-2026-55555",
        source="nvd",
        description="test",
        cvss_score=9.0,
        cvss_severity="CRITICAL",
        cvss_version="3.1",
        published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        last_modified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        cwe_ids=[],
        affected_cpes=[],
        references=[],
        raw_data={"id": "CVE-2026-55555"},
        is_rejected=False,
    )


def test_viewer_cannot_trigger_sync(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.post(
        "/api/v1/threat-intel/sync/cve/CVE-2026-55555",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_viewer_can_read_vulnerabilities(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.get("/api/v1/threat-intel/vulnerabilities", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_analyst_can_trigger_sync_when_enabled(client, db_session, monkeypatch):
    from app.config import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("NVD_ENABLED", "true")
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)

    with patch("app.threat_intel.router.NVDProvider.fetch_cve", return_value=_fake_record()):
        resp = client.post(
            "/api/v1/threat-intel/sync/cve/CVE-2026-55555",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["cve_id"] == "CVE-2026-55555"
    settings_module.get_settings.cache_clear()


def test_sync_disabled_by_default(client, db_session):
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)
    resp = client.post(
        "/api/v1/threat-intel/sync/cve/CVE-2026-55555",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 503


def test_sync_endpoint_is_rate_limited(client, db_session, monkeypatch):
    """The sync endpoint makes a real outbound HTTP call and can block a
    worker thread -- it must be rate limited like login is, so it can't
    be used to hammer NVD's API or exhaust this server's thread pool.

    THREAT_INTEL_SYNC_RATE_LIMIT is read once at router import time
    (the same convention app/auth/router.py already uses for
    LOGIN_RATE_LIMIT), so this test exercises the real configured
    default (10/minute) by sending more than that, rather than trying
    to override it via env var post-import."""
    from app.config import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("NVD_ENABLED", "true")
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)

    with patch("app.threat_intel.router.NVDProvider.fetch_cve", return_value=_fake_record()):
        statuses = [
            client.post(
                "/api/v1/threat-intel/sync/cve/CVE-2026-55555",
                headers={"Authorization": f"Bearer {token}"},
            ).status_code
            for _ in range(15)
        ]

    assert 429 in statuses
    settings_module.get_settings.cache_clear()
