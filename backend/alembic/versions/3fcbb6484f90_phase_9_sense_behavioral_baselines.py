"""phase 9 sense: behavioral baselines

Revision ID: 3fcbb6484f90
Revises: 12b7ca8e4382
Create Date: 2026-09-12 19:21:23.755165

`BehavioralBaseline` (app/sense/models.py) existed with no migration at
all prior to this -- `alembic upgrade head` against a fresh database
never created this table, so every Sense operation (compute_baseline,
evaluate_asset, evaluate_all_assets, and the background scheduler's
sense loop) would fail with "relation does not exist" in any real
deployment. Caught by comparing Base.metadata against an
alembic-migrated schema directly; the test suite never surfaces this
since it bootstraps schema via Base.metadata.create_all() rather than
running migrations.

metric_type reuses the `metrictype` Postgres enum type created by the
phase 3 (monitoring_samples) migration -- create_type=False so this
migration does not attempt to CREATE TYPE a second time.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '3fcbb6484f90'
down_revision = '12b7ca8e4382'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'behavioral_baselines',
        sa.Column('asset_id', sa.String(), nullable=False),
        sa.Column(
            'metric_type',
            postgresql.ENUM('AVAILABILITY', 'LATENCY_MS', 'PACKET_LOSS_PCT', name='metrictype', create_type=False),
            nullable=False,
        ),
        sa.Column('sample_count', sa.Integer(), nullable=False),
        sa.Column('average_value', sa.Float(), nullable=False),
        sa.Column('stddev_value', sa.Float(), nullable=False),
        sa.Column('min_value', sa.Float(), nullable=False),
        sa.Column('max_value', sa.Float(), nullable=False),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_usable', sa.Boolean(), nullable=False),
        sa.Column('notes', sa.String(length=512), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_behavioral_baselines_asset_id'), 'behavioral_baselines', ['asset_id'], unique=False)
    op.create_index(op.f('ix_behavioral_baselines_metric_type'), 'behavioral_baselines', ['metric_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_behavioral_baselines_metric_type'), table_name='behavioral_baselines')
    op.drop_index(op.f('ix_behavioral_baselines_asset_id'), table_name='behavioral_baselines')
    op.drop_table('behavioral_baselines')
