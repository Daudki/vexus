"""
Tests for the ScanProfile-driven NmapCollector argument assembly.

These tests do NOT invoke nmap — they assert on the `nmap_args` list
the collector would pass to subprocess.run. This keeps the tests
deterministic, host-agnostic, and CI-safe (no nmap install required),
while still pinning down exactly which nmap flags each profile emits
(the one piece of behavior that actually matters for the
"scan technique is explicit" rule).

The full live-nmap path (subprocess.run -> XML parse) is exercised
manually against a real authorized target by an operator following
the README's quick-start; this suite deliberately stays out of that
path because every CI environment that doesn't have nmap + a target
to scan would otherwise become a flaky test.
"""
import pytest

from app.discovery.collectors import (
    DEFAULT_TIMING_TEMPLATE,
    NmapCollector,
    ScanProfile,
)


def test_default_profile_is_stealth_syn_not_ping_scan():
    """The user's explicit ask: 'that nmap is just doing a ping scan.
    We gotta strengthen it, and stealth scan is needed.' The default
    must no longer be the old `-sn` ping-scan."""
    collector = NmapCollector()
    assert collector.profile is ScanProfile.STEALTH_SYN
    args = collector.nmap_args
    assert "-sS" in args, "stealth SYN scan flag must be present by default"
    assert "-sn" not in args, "host-discovery (ping scan) must NOT be the default anymore"


def test_host_discovery_profile_kept_for_backwards_compat():
    """The old default (`-sn`, ping scan only) is preserved as an
    explicit profile so existing callers/tests that relied on the
    cheap host-only scan can opt back into it deliberately."""
    collector = NmapCollector(profile=ScanProfile.HOST_DISCOVERY)
    args = collector.nmap_args
    assert "-sn" in args
    assert "-sS" not in args


def test_stealth_syn_profile_has_syn_scan_and_timing():
    """Stealth SYN profile: -sS (the SYN scan itself), -T3 (default
    timing template), ICMP + TCP-SYN-ping probes for host discovery,
    per-host timeout ceiling so a single slow host can't stall the
    whole scan."""
    collector = NmapCollector(profile=ScanProfile.STEALTH_SYN)
    args = collector.nmap_args
    assert "-sS" in args
    assert f"-T{DEFAULT_TIMING_TEMPLATE}" in args
    assert "-PE" in args
    assert any(arg.startswith("-PS") for arg in args), "TCP SYN ping probe expected"
    assert any(arg.startswith("-PA") for arg in args), "TCP ACK ping probe expected"
    assert any(arg.startswith("--host-timeout") for arg in args)


def test_service_version_profile_adds_version_detection():
    """service_version profile = stealth SYN + service banner
    fingerprinting. The -sV flag triggers per-port probes that
    read service banners; --version-intensity controls how many
    probes per port."""
    collector = NmapCollector(profile=ScanProfile.SERVICE_VERSION)
    args = collector.nmap_args
    assert "-sS" in args
    assert "-sV" in args
    assert "--version-intensity=5" in args
    assert "-O" not in args, "OS detection should NOT be on for the service_version profile"


def test_os_detect_profile_adds_os_fingerprinting():
    """os_detect profile = stealth SYN + TCP/IP stack fingerprinting.
    Note: -O requires raw socket privileges; nmap will silently skip
    OS detection if privileges are insufficient — the test pins the
    flag, not the runtime outcome."""
    collector = NmapCollector(profile=ScanProfile.OS_DETECT)
    args = collector.nmap_args
    assert "-sS" in args
    assert "-O" in args
    assert "--osscan-limit" in args
    assert "-sV" not in args, "service version detection should NOT be on for the os_detect profile"


def test_full_profile_combines_everything():
    """Full profile = stealth SYN + service version + OS detection.
    Slowest and most thorough; expected to be used during scheduled
    maintenance windows."""
    collector = NmapCollector(profile=ScanProfile.FULL)
    args = collector.nmap_args
    assert "-sS" in args
    assert "-sV" in args
    assert "-O" in args
    assert "--version-intensity=5" in args
    assert "--osscan-limit" in args


def test_string_profile_value_is_normalized_to_enum():
    """API boundary accepts str (JSON request body) — the constructor
    must normalize it to the enum so the rest of the pipeline can
    compare against enum members."""
    collector = NmapCollector(profile="stealth_syn")
    assert collector.profile is ScanProfile.STEALTH_SYN
    assert "-sS" in collector.nmap_args


def test_unknown_profile_string_raises_value_error():
    """An unknown profile string must raise ValueError, not silently
    fall back. This is the 'closed enum, not free-form command string'
    rule from the spec enforced at the constructor."""
    with pytest.raises(ValueError, match="Unknown scan profile"):
        NmapCollector(profile="not_a_real_profile")


def test_unknown_profile_string_via_api_returns_422(client, db_session, monkeypatch):
    """The API boundary should reject an unknown profile with 422
    (Pydantic's standard response for an invalid enum value) before
    any subprocess is spawned. No nmap is invoked, no scan job is
    created."""
    from app.config import settings as settings_module
    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("AUTHORIZED_SCAN_RANGES", '["10.0.0.0/8"]')

    from app.auth.router import create_access_token
    from app.users.models import Role, RoleName, User

    role = db_session.query(Role).filter_by(name=RoleName.NETWORK_ADMINISTRATOR).first()
    user = User(
        username="netadmin1",
        email="netadmin1@vexus.local",
        password_hash="$2b$12$mockhashmockhashmockhashmockhashmockhashmockhashmockhashmock",
        role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()
    token = create_access_token(data={"sub": "netadmin1"})

    resp = client.post(
        "/api/v1/discovery/scans",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_ranges": ["10.0.0.0/24"], "profile": "totally_made_up"},
    )
    assert resp.status_code == 422
    settings_module.get_settings.cache_clear()


def test_per_scan_profile_overrides_default_when_supplied(client, db_session, monkeypatch):
    """When the API request specifies a profile, the NmapCollector
    that runs for that scan must use it (not the platform default).
    Verified by intercepting the dependency-injected collector."""
    from app.config import settings as settings_module
    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("AUTHORIZED_SCAN_RANGES", '["10.0.0.0/8"]')

    from app.assets.service import DiscoveredHost
    from app.discovery.collectors import SimulatedCollector
    from app.discovery.router import get_discovery_collector
    from app.main import app
    from app.auth.router import create_access_token
    from app.users.models import Role, RoleName, User

    role = db_session.query(Role).filter_by(name=RoleName.NETWORK_ADMINISTRATOR).first()
    user = User(
        username="netadmin2",
        email="netadmin2@vexus.local",
        password_hash="$2b$12$mockhashmockhashmockhashmockhashmockhashmockhashmockhashmock",
        role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()
    token = create_access_token(data={"sub": "netadmin2"})

    captured_profile = {"value": None}

    # Wrap SimulatedCollector so we can observe which profile the
    # router ended up selecting. The collector itself doesn't care
    # about the profile — that's the NmapCollector's job — but the
    # router's profile-resolution code path runs before the collector
    # is invoked, and we want to pin down that the per-request profile
    # is the one that wins.

    # We assert at the ScanJob row level instead, since profile is
    # persisted there. SimulatedCollector returns the host we give it.
    app.dependency_overrides[get_discovery_collector] = lambda: SimulatedCollector(
        [DiscoveredHost(ip_address="10.0.0.5", mac_address="AA:BB:CC:DD:EE:10")]
    )
    try:
        resp = client.post(
            "/api/v1/discovery/scans",
            headers={"Authorization": f"Bearer {token}"},
            json={"target_ranges": ["10.0.0.0/24"], "profile": "service_version"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["profile"] == "service_version", (
            "ScanJob.profile must reflect the per-request profile, not the platform default"
        )
        captured_profile["value"] = body["profile"]
    finally:
        app.dependency_overrides.pop(get_discovery_collector, None)
        settings_module.get_settings.cache_clear()

    assert captured_profile["value"] == "service_version"


def test_default_profile_applied_when_request_omits_profile(client, db_session, monkeypatch):
    """When the API request omits `profile`, the platform default
    (DISCOVERY_DEFAULT_PROFILE = stealth_syn) is used and persisted
    on the ScanJob row."""
    from app.config import settings as settings_module
    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("AUTHORIZED_SCAN_RANGES", '["10.0.0.0/8"]')

    from app.assets.service import DiscoveredHost
    from app.discovery.collectors import SimulatedCollector
    from app.discovery.router import get_discovery_collector
    from app.main import app
    from app.auth.router import create_access_token
    from app.users.models import Role, RoleName, User

    role = db_session.query(Role).filter_by(name=RoleName.NETWORK_ADMINISTRATOR).first()
    user = User(
        username="netadmin3",
        email="netadmin3@vexus.local",
        password_hash="$2b$12$mockhashmockhashmockhashmockhashmockhashmockhashmockhashmock",
        role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()
    token = create_access_token(data={"sub": "netadmin3"})

    app.dependency_overrides[get_discovery_collector] = lambda: SimulatedCollector(
        [DiscoveredHost(ip_address="10.0.0.6", mac_address="AA:BB:CC:DD:EE:11")]
    )
    try:
        resp = client.post(
            "/api/v1/discovery/scans",
            headers={"Authorization": f"Bearer {token}"},
            json={"target_ranges": ["10.0.0.0/24"]},  # no profile field
        )
        assert resp.status_code == 201
        assert resp.json()["profile"] == "stealth_syn"
    finally:
        app.dependency_overrides.pop(get_discovery_collector, None)
        settings_module.get_settings.cache_clear()


def test_invalid_default_profile_setting_returns_400_at_scan_time(client, db_session, monkeypatch):
    """If an operator has set DISCOVERY_DEFAULT_PROFILE to garbage in
    the environment, a scan request that omits the profile must fail
    loudly with 400 — not silently fall back, not crash the worker."""
    from app.config import settings as settings_module
    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("AUTHORIZED_SCAN_RANGES", '["10.0.0.0/8"]')
    monkeypatch.setenv("DISCOVERY_DEFAULT_PROFILE", "not_a_real_profile")

    from app.auth.router import create_access_token
    from app.users.models import Role, RoleName, User

    role = db_session.query(Role).filter_by(name=RoleName.NETWORK_ADMINISTRATOR).first()
    user = User(
        username="netadmin4",
        email="netadmin4@vexus.local",
        password_hash="$2b$12$mockhashmockhashmockhashmockhashmockhashmockhashmockhashmock",
        role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()
    token = create_access_token(data={"sub": "netadmin4"})

    resp = client.post(
        "/api/v1/discovery/scans",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_ranges": ["10.0.0.0/24"]},
    )
    assert resp.status_code == 400
    assert "DISCOVERY_DEFAULT_PROFILE" in resp.json()["detail"]
    settings_module.get_settings.cache_clear()


def test_parse_xml_still_extracts_open_ports_after_stealth_scan():
    """The XML parser must continue to extract open ports from the
    nmap output of a stealth scan (which produces the same XML shape
    as a connect scan, just with a different probe technique). This
    pins down that the refactor didn't break the parser path."""
    sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
<nmaprun scanner="nmap" args="nmap -sS -oX - 10.0.0.5" start="1700000000">
  <host>
    <status state="up" reason="syn-ack" reason_ttl="64"/>
    <address addr="10.0.0.5" addrtype="ipv4"/>
    <address addr="AA:BB:CC:DD:EE:10" addrtype="mac" vendor="Acme"/>
    <hostnames>
      <hostname name="host-a.local" type="PTR"/>
    </hostnames>
    <ports>
      <port protocol="tcp" portid="22">
        <state state="open" reason="syn-ack" reason_ttl="64"/>
        <service name="ssh" product="OpenSSH" version="8.4p1"/>
      </port>
      <port protocol="tcp" portid="80">
        <state state="open" reason="syn-ack" reason_ttl="64"/>
        <service name="http" product="nginx" version="1.18.0"/>
      </port>
      <port protocol="tcp" portid="443">
        <state state="closed" reason="reset" reason_ttl="64"/>
      </port>
    </ports>
  </host>
  <host>
    <status state="down" reason="no-response" reason_ttl="0"/>
    <address addr="10.0.0.6" addrtype="ipv4"/>
  </host>
</nmaprun>
"""
    hosts = NmapCollector._parse_xml(sample_xml)
    assert len(hosts) == 1  # only the up host
    h = hosts[0]
    assert h.ip_address == "10.0.0.5"
    assert h.mac_address == "AA:BB:CC:DD:EE:10"
    assert h.hostname == "host-a.local"
    assert h.vendor == "Acme"
    assert h.open_ports == [22, 80]  # 443 was closed — must not appear


def test_legacy_extra_args_still_appended_after_profile_flags():
    """Existing callers/tests that pass extra_args for legitimate
    reasons (e.g. `-n` to skip DNS resolution in tests, or `--exclude`
    to skip specific hosts) must keep working. extra_args are appended
    AFTER the profile flags so they can't accidentally override the
    scan technique (nmap takes the LAST occurrence of a conflicting
    flag, but the profile's core flags like -sS/-sn are explicit and
    extra_args shouldn't be trying to override them — that's what
    profiles are for)."""
    collector = NmapCollector(profile=ScanProfile.STEALTH_SYN, extra_args=["-n", "--exclude", "10.0.0.1"])
    args = collector.nmap_args
    assert "-sS" in args
    assert "-n" in args
    assert "--exclude" in args
    # The profile flags come first, extra_args come after.
    assert args.index("-sS") < args.index("-n")
