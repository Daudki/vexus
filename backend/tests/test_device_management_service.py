from datetime import datetime, timedelta, timezone

import pytest

from app.assets.models import Asset, AssetStatus, AssetTrustStatus
from app.core.security import hash_password
from app.device_management.models import DeviceActionType, ManagedDevice, ManagedDeviceStatus
from app.device_management.service import DeviceManagementError, DeviceManagementService, PolicyError
from app.events.models import NetworkEvent
from app.users.models import Role, RoleName, User


def _seed_asset(db_session, hostname="host-1"):
    now = datetime.now(timezone.utc)
    asset = Asset(
        hostname=hostname,
        ip_address="10.0.0.5",
        status=AssetStatus.ONLINE,
        trust_status=AssetTrustStatus.UNKNOWN,
        first_seen=now,
        last_seen=now,
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def _seed_user(db_session, role_name, username="user1"):
    role = db_session.query(Role).filter_by(name=role_name).first()
    user = User(username=username, email=f"{username}@vexus.local", password_hash=hash_password("x"), role_id=role.id)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_enroll_device_returns_plaintext_token_once(db_session):
    asset = _seed_asset(db_session)
    admin = _seed_user(db_session, RoleName.ADMIN)

    device, token = DeviceManagementService(db_session).enroll_device(asset.id, admin)

    assert device.status == ManagedDeviceStatus.PENDING_ENROLLMENT
    assert len(token) > 20
    assert device.enrollment_token_hash is not None
    assert device.enrollment_token_hash != token


def test_complete_enrollment_activates_device(db_session):
    asset = _seed_asset(db_session)
    admin = _seed_user(db_session, RoleName.ADMIN)
    service = DeviceManagementService(db_session)
    _, token = service.enroll_device(asset.id, admin)

    device, agent_token = service.complete_enrollment(token, "1.0.0", "Ubuntu 24.04")

    assert device.status == ManagedDeviceStatus.ACTIVE
    assert device.agent_version == "1.0.0"
    assert device.enrollment_token_hash is None
    assert len(agent_token) > 20


def test_complete_enrollment_rejects_reused_token(db_session):
    asset = _seed_asset(db_session)
    admin = _seed_user(db_session, RoleName.ADMIN)
    service = DeviceManagementService(db_session)
    _, token = service.enroll_device(asset.id, admin)
    service.complete_enrollment(token, None, None)

    with pytest.raises(DeviceManagementError, match="Invalid or already-used"):
        service.complete_enrollment(token, None, None)


def test_complete_enrollment_rejects_expired_token(db_session):
    asset = _seed_asset(db_session)
    admin = _seed_user(db_session, RoleName.ADMIN)
    service = DeviceManagementService(db_session)
    device, token = service.enroll_device(asset.id, admin)

    device.enrollment_token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    with pytest.raises(DeviceManagementError, match="expired"):
        service.complete_enrollment(token, None, None)


def test_queue_task_rejects_insufficient_role(db_session):
    asset = _seed_asset(db_session)
    admin = _seed_user(db_session, RoleName.ADMIN, "admin1")
    viewer = _seed_user(db_session, RoleName.VIEWER, "viewer1")
    service = DeviceManagementService(db_session)
    device, token = service.enroll_device(asset.id, admin)
    service.complete_enrollment(token, None, None)

    with pytest.raises(PolicyError):
        service.queue_task(device.id, DeviceActionType.STATUS_CHECK, {}, viewer, confirm=False)


def test_queue_reboot_without_confirm_is_rejected(db_session):
    asset = _seed_asset(db_session)
    admin = _seed_user(db_session, RoleName.ADMIN)
    service = DeviceManagementService(db_session)
    device, token = service.enroll_device(asset.id, admin)
    service.complete_enrollment(token, None, None)

    with pytest.raises(PolicyError, match="requires confirm"):
        service.queue_task(device.id, DeviceActionType.REBOOT, {}, admin, confirm=False)


def test_queue_reboot_with_confirm_succeeds(db_session):
    asset = _seed_asset(db_session)
    admin = _seed_user(db_session, RoleName.ADMIN)
    service = DeviceManagementService(db_session)
    device, token = service.enroll_device(asset.id, admin)
    service.complete_enrollment(token, None, None)

    task = service.queue_task(device.id, DeviceActionType.REBOOT, {}, admin, confirm=True)
    assert task.confirmed is True


def test_queue_task_on_unenrolled_device_is_rejected(db_session):
    asset = _seed_asset(db_session)
    admin = _seed_user(db_session, RoleName.ADMIN)
    service = DeviceManagementService(db_session)
    device, _ = service.enroll_device(asset.id, admin)

    with pytest.raises(DeviceManagementError, match="not enrolled and active"):
        service.queue_task(device.id, DeviceActionType.STATUS_CHECK, {}, admin, confirm=False)


def test_agent_cannot_report_result_for_another_devices_task(db_session):
    asset_a = _seed_asset(db_session, "host-a")
    asset_b = _seed_asset(db_session, "host-b")
    admin = _seed_user(db_session, RoleName.ADMIN)
    service = DeviceManagementService(db_session)

    device_a, token_a = service.enroll_device(asset_a.id, admin)
    service.complete_enrollment(token_a, None, None)
    device_b, token_b = service.enroll_device(asset_b.id, admin)
    device_b, _ = service.complete_enrollment(token_b, None, None)

    task = service.queue_task(device_a.id, DeviceActionType.STATUS_CHECK, {}, admin, confirm=False)

    with pytest.raises(DeviceManagementError, match="Task not found"):
        service.report_result(device_b, task.id, True, "ok", "")


def test_state_changing_action_emits_network_event(db_session):
    asset = _seed_asset(db_session)
    admin = _seed_user(db_session, RoleName.ADMIN)
    service = DeviceManagementService(db_session)
    device, token = service.enroll_device(asset.id, admin)
    device, _ = service.complete_enrollment(token, None, None)

    task = service.queue_task(device.id, DeviceActionType.REBOOT, {}, admin, confirm=True)
    service.report_result(device, task.id, True, "rebooted", "")

    events = db_session.query(NetworkEvent).filter_by(asset_id=asset.id).all()
    assert len(events) == 1
    assert events[0].event_type == "DEVICE_REBOOT"


def test_status_check_does_not_emit_network_event(db_session):
    asset = _seed_asset(db_session)
    admin = _seed_user(db_session, RoleName.ADMIN)
    service = DeviceManagementService(db_session)
    device, token = service.enroll_device(asset.id, admin)
    device, _ = service.complete_enrollment(token, None, None)

    task = service.queue_task(device.id, DeviceActionType.STATUS_CHECK, {}, admin, confirm=False)
    service.report_result(device, task.id, True, "ok", "")

    assert db_session.query(NetworkEvent).filter_by(asset_id=asset.id).count() == 0


def test_revoke_clears_agent_credential(db_session):
    asset = _seed_asset(db_session)
    admin = _seed_user(db_session, RoleName.ADMIN)
    service = DeviceManagementService(db_session)
    device, token = service.enroll_device(asset.id, admin)
    device, _ = service.complete_enrollment(token, None, None)

    revoked = service.revoke_device(device.id, admin)
    assert revoked.status == ManagedDeviceStatus.REVOKED
    assert revoked.agent_token_hash is None


def test_get_next_task_returns_oldest_pending_first(db_session):
    asset = _seed_asset(db_session)
    admin = _seed_user(db_session, RoleName.ADMIN)
    service = DeviceManagementService(db_session)
    device, token = service.enroll_device(asset.id, admin)
    device, _ = service.complete_enrollment(token, None, None)

    first = service.queue_task(device.id, DeviceActionType.STATUS_CHECK, {}, admin, confirm=False)
    service.queue_task(device.id, DeviceActionType.INVENTORY_SYNC, {}, admin, confirm=False)

    next_task = service.get_next_task(device)
    assert next_task.id == first.id
