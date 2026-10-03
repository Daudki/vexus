"""Add profile column to scan_jobs (ScanProfile enum).

Revises: 1ce5028f5857
Create Date: 2026-10-02 00:00:00
"""
from alembic import op
import sqlalchemy as sa

from app.discovery.collectors import ScanProfile


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "1ce5028f5857"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the new enum type. SQLite doesn't have a real ENUM type
    # — SQLAlchemy stores it as VARCHAR with a CHECK constraint when
    # using batch_alter_table, which is what we use below for SQLite
    # portability (see docs/KNOWLEDGE_TRANSFER.md §11).
    # For Postgres the Enum is created as a real type once here.
    scan_profile_enum = sa.Enum(ScanProfile, name="scan_profile")

    # Use batch_alter_table so this migration applies cleanly on SQLite
    # (which has very limited native ALTER) as well as Postgres.
    with op.batch_alter_table("scan_jobs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "profile",
                scan_profile_enum,
                nullable=False,
                server_default=ScanProfile.STEALTH_SYN.value,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("scan_jobs", schema=None) as batch_op:
        batch_op.drop_column("profile")
    # Drop the enum type on Postgres; no-op on SQLite (it never
    # existed as a separate type).
    sa.Enum(name="scan_profile").drop(op.get_bind(), checkfirst=True)
