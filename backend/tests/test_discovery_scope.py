import pytest

from app.discovery.scope import ScopeError, validate_target_ranges


def test_empty_target_list_raises(monkeypatch):
    with pytest.raises(ScopeError, match="No target ranges"):
        validate_target_ranges([])


def test_no_authorized_ranges_configured_refuses_everything(monkeypatch):
    from app.config import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("AUTHORIZED_SCAN_RANGES", "[]")
    monkeypatch.setenv("SECRET_KEY", "test-secret")

    with pytest.raises(ScopeError, match="No authorized scan ranges"):
        validate_target_ranges(["10.0.0.0/24"])

    settings_module.get_settings.cache_clear()


def test_target_within_authorized_range_passes(monkeypatch):
    from app.config import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("AUTHORIZED_SCAN_RANGES", '["10.0.0.0/8"]')
    monkeypatch.setenv("SECRET_KEY", "test-secret")

    validate_target_ranges(["10.0.0.0/24"])  # should not raise

    settings_module.get_settings.cache_clear()


def test_target_outside_authorized_range_is_refused(monkeypatch):
    from app.config import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("AUTHORIZED_SCAN_RANGES", '["10.0.0.0/8"]')
    monkeypatch.setenv("SECRET_KEY", "test-secret")

    with pytest.raises(ScopeError, match="not within any authorized"):
        validate_target_ranges(["192.168.1.0/24"])

    settings_module.get_settings.cache_clear()


def test_invalid_cidr_is_rejected(monkeypatch):
    from app.config import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("AUTHORIZED_SCAN_RANGES", '["10.0.0.0/8"]')
    monkeypatch.setenv("SECRET_KEY", "test-secret")

    with pytest.raises(ScopeError, match="not a valid IP address"):
        validate_target_ranges(["not-an-ip"])

    settings_module.get_settings.cache_clear()


def test_dangerously_broad_authorized_range_is_ignored(monkeypatch):
    """0.0.0.0/0 (or anything broader than /8) must never actually
    become an authorized range, even if an operator puts it in config —
    that would silently defeat the entire point of an authorized-ranges
    allowlist."""
    from app.config import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("AUTHORIZED_SCAN_RANGES", '["0.0.0.0/0"]')
    monkeypatch.setenv("SECRET_KEY", "test-secret")

    with pytest.raises(ScopeError, match="No authorized scan ranges"):
        validate_target_ranges(["8.8.8.8/32"])

    settings_module.get_settings.cache_clear()


def test_authorized_range_wider_than_slash_8_is_ignored(monkeypatch):
    from app.config import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("AUTHORIZED_SCAN_RANGES", '["10.0.0.0/7"]')
    monkeypatch.setenv("SECRET_KEY", "test-secret")

    with pytest.raises(ScopeError, match="No authorized scan ranges"):
        validate_target_ranges(["10.0.0.0/24"])

    settings_module.get_settings.cache_clear()


def test_authorized_slash_8_is_still_allowed(monkeypatch):
    """The whole 10.0.0.0/8 RFC1918 block is a legitimate, common
    real-world authorization -- the ceiling must not reject exactly the
    boundary case."""
    from app.config import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("AUTHORIZED_SCAN_RANGES", '["10.0.0.0/8"]')
    monkeypatch.setenv("SECRET_KEY", "test-secret")

    validate_target_ranges(["10.5.5.0/24"])  # should not raise

    settings_module.get_settings.cache_clear()


def test_broad_range_mixed_with_valid_range_only_ignores_the_broad_one(monkeypatch):
    from app.config import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("AUTHORIZED_SCAN_RANGES", '["0.0.0.0/0", "192.168.1.0/24"]')
    monkeypatch.setenv("SECRET_KEY", "test-secret")

    validate_target_ranges(["192.168.1.0/24"])  # the valid entry still works
    with pytest.raises(ScopeError):
        validate_target_ranges(["8.8.8.8/32"])  # but nothing outside it is authorized

    settings_module.get_settings.cache_clear()
