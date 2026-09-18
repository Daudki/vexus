"""phase 10 simulation: asset is_synthetic flag

Revision ID: 6efc6543c092
Revises: 7f8c1d2e4a10
Create Date: 2026-09-14 19:04:21.913579

Alert and Incident already carry `is_synthetic` (added in the phase 6/7
migrations); Asset was the one entity in the pipeline still missing it,
needed before Simulation Mode (docs/vexus-v2.md, domain 14) can create
fully self-contained simulated scenarios. Indexed to match the existing
`ix_network_events_is_synthetic` precedent, since this is the same kind
of frequently-filtered boolean (every list endpoint now defaults to
excluding synthetic rows).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6efc6543c092'
down_revision = '7f8c1d2e4a10'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index(op.f("ix_assets_is_synthetic"), "assets", ["is_synthetic"], unique=False)
    # server_default stays in place permanently (unlike a throwaway
    # backfill default) -- it's harmless, and dropping it would need
    # op.batch_alter_table for SQLite portability (SQLite has no native
    # ALTER COLUMN), which isn't worth the added risk for a purely
    # cosmetic cleanup.


def downgrade() -> None:
    op.drop_index(op.f("ix_assets_is_synthetic"), table_name="assets")
    op.drop_column("assets", "is_synthetic")
