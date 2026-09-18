"""phase 11 device management: managed devices and tasks

Revision ID: 1ce5028f5857
Revises: 6efc6543c092
Create Date: 2026-09-17 20:11:34.563266

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1ce5028f5857'
down_revision = '6efc6543c092'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "managed_devices",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("asset_id", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending_enrollment", "active", "revoked", name="manageddevicestatus"),
            nullable=False,
        ),
        sa.Column("enrollment_token_hash", sa.String(length=64), nullable=True),
        sa.Column("enrollment_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agent_token_hash", sa.String(length=64), nullable=True),
        sa.Column("last_checkin_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agent_version", sa.String(length=64), nullable=True),
        sa.Column("reported_os", sa.String(length=128), nullable=True),
        sa.Column("enrolled_by_user_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.ForeignKeyConstraint(["enrolled_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_managed_devices_asset_id"), "managed_devices", ["asset_id"], unique=True)
    op.create_index(
        op.f("ix_managed_devices_enrollment_token_hash"), "managed_devices", ["enrollment_token_hash"], unique=False
    )
    op.create_index(
        op.f("ix_managed_devices_agent_token_hash"), "managed_devices", ["agent_token_hash"], unique=False
    )

    op.create_table(
        "device_tasks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("managed_device_id", sa.String(), nullable=False),
        sa.Column(
            "action_type",
            sa.Enum(
                "status_check", "inventory_sync", "service_restart", "reboot", "isolate", name="deviceactiontype"
            ),
            nullable=False,
        ),
        sa.Column("params", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "completed", "failed", "rejected", name="devicetaskstatus"),
            nullable=False,
        ),
        sa.Column("requested_by_user_id", sa.String(), nullable=True),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("error_message", sa.String(length=1024), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["managed_device_id"], ["managed_devices.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_device_tasks_managed_device_id"), "device_tasks", ["managed_device_id"], unique=False)
    op.create_index(op.f("ix_device_tasks_status"), "device_tasks", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_device_tasks_status"), table_name="device_tasks")
    op.drop_index(op.f("ix_device_tasks_managed_device_id"), table_name="device_tasks")
    op.drop_table("device_tasks")

    op.drop_index(op.f("ix_managed_devices_agent_token_hash"), table_name="managed_devices")
    op.drop_index(op.f("ix_managed_devices_enrollment_token_hash"), table_name="managed_devices")
    op.drop_index(op.f("ix_managed_devices_asset_id"), table_name="managed_devices")
    op.drop_table("managed_devices")
