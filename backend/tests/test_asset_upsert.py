from app.assets.models import AssetChangeType, AssetTrustStatus
from app.assets.service import AssetService, DiscoveredHost
from app.events.models import NetworkEvent


def test_first_sighting_creates_asset_as_unknown_not_untrusted(db_session):
    service = AssetService(db_session)
    host = DiscoveredHost(ip_address="10.0.0.5", mac_address="AA:BB:CC:DD:EE:01", hostname="printer-1")

    result = service.upsert_from_discovery(host)

    assert result.is_new is True
    # An unknown asset is not automatically malicious/untrusted.
    assert result.asset.trust_status == AssetTrustStatus.UNKNOWN
    assert result.changes == [AssetChangeType.FIRST_DISCOVERED]


def test_first_sighting_writes_history_and_new_device_event(db_session):
    service = AssetService(db_session)
    host = DiscoveredHost(ip_address="10.0.0.6", mac_address="AA:BB:CC:DD:EE:02")

    result = service.upsert_from_discovery(host)

    history = service.repo.get_history(result.asset.id)
    assert len(history) == 1
    assert history[0].change_type == AssetChangeType.FIRST_DISCOVERED

    events = db_session.query(NetworkEvent).filter_by(asset_id=result.asset.id).all()
    assert len(events) == 1
    assert events[0].event_type == "NEW_DEVICE"
    assert events[0].confidence == 1.0


def test_second_sighting_with_no_changes_does_not_duplicate_history(db_session):
    service = AssetService(db_session)
    host = DiscoveredHost(ip_address="10.0.0.7", mac_address="AA:BB:CC:DD:EE:03", hostname="host-a")

    first = service.upsert_from_discovery(host)
    second = service.upsert_from_discovery(host)

    assert second.is_new is False
    assert second.changes == []

    history = service.repo.get_history(first.asset.id)
    assert len(history) == 1  # only the original FIRST_DISCOVERED entry


def test_ip_change_is_tracked_as_history_and_event(db_session):
    service = AssetService(db_session)
    host_v1 = DiscoveredHost(ip_address="10.0.0.8", mac_address="AA:BB:CC:DD:EE:04")
    host_v2 = DiscoveredHost(ip_address="10.0.0.99", mac_address="AA:BB:CC:DD:EE:04")

    first = service.upsert_from_discovery(host_v1)
    second = service.upsert_from_discovery(host_v2)

    assert second.is_new is False
    assert AssetChangeType.IP_CHANGED in second.changes
    assert second.asset.ip_address == "10.0.0.99"

    history = service.repo.get_history(first.asset.id)
    change_types = [h.change_type for h in history]
    assert AssetChangeType.IP_CHANGED in change_types

    events = db_session.query(NetworkEvent).filter_by(asset_id=first.asset.id, event_type="IP_CHANGED").all()
    assert len(events) == 1


def test_matches_existing_asset_by_ip_when_no_mac_available(db_session):
    """Some discovery methods (e.g. a plain ping scan) may not yield a MAC.
    Falling back to IP matching should still recognize the same host."""
    service = AssetService(db_session)
    host_with_mac = DiscoveredHost(ip_address="10.0.0.10", mac_address="AA:BB:CC:DD:EE:05")
    host_without_mac = DiscoveredHost(ip_address="10.0.0.10", mac_address=None)

    first = service.upsert_from_discovery(host_with_mac)
    second = service.upsert_from_discovery(host_without_mac)

    assert second.is_new is False
    assert second.asset.id == first.asset.id


def test_equivalent_discovery_identifiers_do_not_create_changes(db_session):
    service = AssetService(db_session)
    first = service.upsert_from_discovery(
        DiscoveredHost(
            ip_address=" 10.0.0.11 ",
            mac_address="AA-BB-CC-DD-EE-06",
            hostname="Host-A.",
        )
    )
    second = service.upsert_from_discovery(
        DiscoveredHost(
            ip_address="10.0.0.11",
            mac_address="aa:bb:cc:dd:ee:06",
            hostname="host-a",
        )
    )

    assert second.asset.id == first.asset.id
    assert second.changes == []
    assert second.asset.mac_address == "aa:bb:cc:dd:ee:06"
    assert second.asset.hostname == "host-a"
