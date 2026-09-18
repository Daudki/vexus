from __future__ import annotations

import enum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ManagedDeviceStatus(str, enum.Enum):
    PENDING_ENROLLMENT = "pending_enrollment"
    ACTIVE = "active"
    REVOKED = "revoked"


class DeviceActionType(str, enum.Enum):
    STATUS_CHECK = "status_check"
    INVENTORY_SYNC = "inventory_sync"
    SERVICE_RESTART = "service_restart"
    REBOOT = "reboot"
    ISOLATE = "isolate"


class DeviceTaskStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class ManagedDevice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "managed_devices"

    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), nullable=False, unique=True, index=True)
    status: Mapped[ManagedDeviceStatus] = mapped_column(
        Enum(ManagedDeviceStatus), default=ManagedDeviceStatus.PENDING_ENROLLMENT, nullable=False
    )

    enrollment_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    enrollment_token_expires_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    agent_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    last_checkin_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    agent_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reported_os: Mapped[str | None] = mapped_column(String(128), nullable=True)

    enrolled_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class DeviceTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "device_tasks"

    managed_device_id: Mapped[str] = mapped_column(ForeignKey("managed_devices.id"), nullable=False, index=True)
    action_type: Mapped[DeviceActionType] = mapped_column(Enum(DeviceActionType), nullable=False)
    params: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    status: Mapped[DeviceTaskStatus] = mapped_column(
        Enum(DeviceTaskStatus), default=DeviceTaskStatus.PENDING, nullable=False, index=True
    )

    requested_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    result: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error_message: Mapped[str] = mapped_column(String(1024), default="", nullable=False)
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
