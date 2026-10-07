"""align schema with models

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-10-07
"""
from alembic import op
import sqlalchemy as sa

revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        op.execute("UPDATE scan_jobs SET profile = 'STEALTH_SYN' WHERE profile = 'stealth_syn'")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE vulnerabilities DROP CONSTRAINT IF EXISTS vulnerabilities_cve_id_key")
    op.create_index("ix_audit_logs_target", "audit_logs", ["target_type", "target_id"])
    with op.batch_alter_table("roles") as batch:
        batch.alter_column(
            "description",
            existing_type=sa.String(length=255),
            type_=sa.Text(),
            existing_nullable=False,
            nullable=True,
        )


def downgrade() -> None:
    op.execute("UPDATE roles SET description = '' WHERE description IS NULL")
    with op.batch_alter_table("roles") as batch:
        batch.alter_column(
            "description",
            existing_type=sa.Text(),
            type_=sa.String(length=255),
            existing_nullable=True,
            nullable=False,
        )
    op.drop_index("ix_audit_logs_target", table_name="audit_logs")
    if op.get_bind().dialect.name == "postgresql":
        op.create_unique_constraint("vulnerabilities_cve_id_key", "vulnerabilities", ["cve_id"])
