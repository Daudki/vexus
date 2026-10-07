"""asset services

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-10-07
"""
from alembic import op
import sqlalchemy as sa

revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_services",
        sa.Column("asset_id", sa.String(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=True),
        sa.Column("product", sa.String(length=128), nullable=True),
        sa.Column("version", sa.String(length=64), nullable=True),
        sa.Column("cpe", sa.String(length=255), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id", "port", "protocol", name="uq_asset_service_port"),
    )
    op.create_index(op.f("ix_asset_services_asset_id"), "asset_services", ["asset_id"])
    op.create_index(op.f("ix_asset_services_cpe"), "asset_services", ["cpe"])


def downgrade() -> None:
    op.drop_index(op.f("ix_asset_services_cpe"), table_name="asset_services")
    op.drop_index(op.f("ix_asset_services_asset_id"), table_name="asset_services")
    op.drop_table("asset_services")
