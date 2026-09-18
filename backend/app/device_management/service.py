from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.assets.models import Asset
from app.audit.service import AuditService
from app.device_management.models import (
    DeviceActionType,
    DeviceTask,
    DeviceTaskStatus,
    ManagedDevice,
    ManagedDeviceStatus,
)
from app.device_management.tokens import generate_token, hash_token
from app.events.models import EventSeverity, EventSource, NetworkEvent
from app.users.models import RoleName, User

ENROLLMENT_TOKEN_TTL_MINUTES = 15

STATE_CHANGING_ACTIONS = {DeviceActionType.SERVICE_RESTART, DeviceActionType.REBOOT, DeviceActionType.ISOLATE}


@dataclass
class ActionPolicy:
    allowed_roles: tuple[RoleName, ...]
    requires_confirm: bool


ACTION_POLICY: dict[DeviceActionType, ActionPolicy] = {
    DeviceActionType.STATUS_CHECK: ActionPolicy(
        (RoleName.ADMIN, RoleName.NETWORK_ADMINISTRATOR, RoleName.SECURITY_ANALYST), False
    ),
    DeviceActionType.INVENTORY_SYNC: ActionPolicy(
        (RoleName.ADMIN, RoleName.NETWORK_ADMINISTRATOR, RoleName.SECURITY_ANALYST), False
    ),
    DeviceActionType.SERVICE_RESTART: ActionPolicy((RoleName.ADMIN, RoleName.NETWORK_ADMINISTRATOR), False),
    DeviceActionType.REBOOT: ActionPolicy((RoleName.ADMIN,), True),
    DeviceActionType.ISOLATE: ActionPolicy((RoleName.ADMIN,), True),
}


class DeviceManagementError(Exception):
    pass


class PolicyError(DeviceManagementError):
    pass


class DeviceManagementService:
    def __init__(self, db: Session):
        self.db = db
        self.audit = AuditService(db)

    def enroll_device(self, asset_id: str, actor: User, ip_address: str = "") -> tuple[ManagedDevice, str]:
        asset = self.db.get(Asset, asset_id)
        if asset is None:
            raise DeviceManagementError(f"Asset '{asset_id}' does not exist.")

        device = self.db.query(ManagedDevice).filter_by(asset_id=asset_id).first()
        if device is None:
            device = ManagedDevice(asset_id=asset_id, enrolled_by_user_id=actor.id)
            self.db.add(device)
        elif device.status == ManagedDeviceStatus.ACTIVE:
            device.agent_token_hash = None

        plaintext_token = generate_token()
        device.enrollment_token_hash = hash_token(plaintext_token)
        device.enrollment_token_expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=ENROLLMENT_TOKEN_TTL_MINUTES
        )
        device.status = ManagedDeviceStatus.PENDING_ENROLLMENT
        self.db.commit()
        self.db.refresh(device)

        self.audit.record(
            action="device_management.enroll_issued",
            actor=actor,
            target_type="managed_device",
            target_id=device.id,
            detail=f"Enrollment token issued for asset '{asset.display_name}'.",
            ip_address=ip_address,
        )
        return device, plaintext_token

    def complete_enrollment(
        self, enrollment_token: str, agent_version: str | None, reported_os: str | None
    ) -> tuple[ManagedDevice, str]:
        token_hash = hash_token(enrollment_token)
        device = (
            self.db.query(ManagedDevice)
            .filter(
                ManagedDevice.enrollment_token_hash == token_hash,
                ManagedDevice.status == ManagedDeviceStatus.PENDING_ENROLLMENT,
            )
            .first()
        )
        if device is None:
            raise DeviceManagementError("Invalid or already-used enrollment token.")
        if device.enrollment_token_expires_at is not None:
            expires_at = device.enrollment_token_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                raise DeviceManagementError("Enrollment token has expired. Request a new one from an admin.")

        plaintext_agent_token = generate_token()
        device.agent_token_hash = hash_token(plaintext_agent_token)
        device.enrollment_token_hash = None
        device.enrollment_token_expires_at = None
        device.status = ManagedDeviceStatus.ACTIVE
        device.agent_version = agent_version
        device.reported_os = reported_os
        device.last_checkin_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(device)

        self.audit.record(
            action="device_management.enrollment_completed",
            actor=None,
            target_type="managed_device",
            target_id=device.id,
            detail=f"Agent enrolled (version={agent_version}, os={reported_os}).",
        )
        return device, plaintext_agent_token

    def revoke_device(self, managed_device_id: str, actor: User, ip_address: str = "") -> ManagedDevice:
        device = self.db.get(ManagedDevice, managed_device_id)
        if device is None:
            raise DeviceManagementError(f"Managed device '{managed_device_id}' does not exist.")

        device.status = ManagedDeviceStatus.REVOKED
        device.agent_token_hash = None
        device.enrollment_token_hash = None
        self.db.commit()
        self.db.refresh(device)

        self.audit.record(
            action="device_management.revoke",
            actor=actor,
            target_type="managed_device",
            target_id=device.id,
            detail="Agent credential revoked.",
            ip_address=ip_address,
        )
        return device

    def queue_task(
        self,
        managed_device_id: str,
        action_type: DeviceActionType,
        params: dict,
        actor: User,
        confirm: bool,
        ip_address: str = "",
    ) -> DeviceTask:
        device = self.db.get(ManagedDevice, managed_device_id)
        if device is None:
            raise DeviceManagementError(f"Managed device '{managed_device_id}' does not exist.")
        if device.status != ManagedDeviceStatus.ACTIVE:
            raise DeviceManagementError("Device is not enrolled and active.")

        policy = ACTION_POLICY[action_type]
        if actor.role.name not in policy.allowed_roles:
            raise PolicyError(f"'{action_type.value}' requires one of: {[r.value for r in policy.allowed_roles]}.")
        if policy.requires_confirm and not confirm:
            raise PolicyError(f"'{action_type.value}' is irreversible and requires confirm=true.")

        task = DeviceTask(
            managed_device_id=managed_device_id,
            action_type=action_type,
            params=json.dumps(params),
            requested_by_user_id=actor.id,
            confirmed=confirm,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        self.audit.record(
            action="device_management.task_queued",
            actor=actor,
            target_type="device_task",
            target_id=task.id,
            detail=f"Queued '{action_type.value}' for device {managed_device_id}.",
            ip_address=ip_address,
        )
        return task

    def get_next_task(self, device: ManagedDevice) -> DeviceTask | None:
        return (
            self.db.query(DeviceTask)
            .filter_by(managed_device_id=device.id, status=DeviceTaskStatus.PENDING)
            .order_by(DeviceTask.created_at.asc())
            .first()
        )

    def report_result(
        self, device: ManagedDevice, task_id: str, success: bool, result: str, error_message: str
    ) -> DeviceTask:
        task = self.db.get(DeviceTask, task_id)
        if task is None or task.managed_device_id != device.id:
            raise DeviceManagementError("Task not found for this device.")
        if task.status != DeviceTaskStatus.PENDING:
            raise DeviceManagementError("Task has already been completed.")

        task.status = DeviceTaskStatus.COMPLETED if success else DeviceTaskStatus.FAILED
        task.result = result
        task.error_message = error_message
        task.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(task)

        self.audit.record(
            action="device_management.task_completed",
            actor=None,
            target_type="device_task",
            target_id=task.id,
            detail=f"'{task.action_type.value}' {task.status.value}: {result[:200]}",
        )

        if success and task.action_type in STATE_CHANGING_ACTIONS:
            self.db.add(
                NetworkEvent(
                    event_type=f"DEVICE_{task.action_type.value.upper()}",
                    event_source=EventSource.MANUAL,
                    timestamp=datetime.now(timezone.utc),
                    asset_id=device.asset_id,
                    severity=EventSeverity.MEDIUM,
                    confidence=1.0,
                    description=f"Device management action '{task.action_type.value}' completed.",
                    evidence=json.dumps([task.id]),
                )
            )
            self.db.commit()

        return task
