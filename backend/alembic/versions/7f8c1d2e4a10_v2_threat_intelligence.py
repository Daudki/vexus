"""v2 threat intelligence vulnerability records

Revision ID: 7f8c1d2e4a10
Revises: 3fcbb6484f90
Create Date: 2026-09-12
"""
from alembic import op
import sqlalchemy as sa

revision = "7f8c1d2e4a10"
down_revision = "3fcbb6484f90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vulnerabilities",
        sa.Column("cve_id", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("cvss_score", sa.Float(), nullable=True),
        sa.Column("cvss_severity", sa.String(length=16), nullable=True),
        sa.Column("cvss_version", sa.String(length=8), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cwe_ids", sa.Text(), nullable=False),
        sa.Column("affected_cpes", sa.Text(), nullable=False),
        sa.Column("references", sa.Text(), nullable=False),
        sa.Column("raw_data", sa.Text(), nullable=False),
        sa.Column("is_rejected", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cve_id"),
    )
    op.create_index(op.f("ix_vulnerabilities_cve_id"), "vulnerabilities", ["cve_id"], unique=True)
    op.create_index(op.f("ix_vulnerabilities_source"), "vulnerabilities", ["source"], unique=False)
    op.create_index(op.f("ix_vulnerabilities_cvss_severity"), "vulnerabilities", ["cvss_severity"], unique=False)
    op.create_index(op.f("ix_vulnerabilities_published_at"), "vulnerabilities", ["published_at"], unique=False)
    op.create_index(op.f("ix_vulnerabilities_last_modified_at"), "vulnerabilities", ["last_modified_at"], unique=False)
    op.create_index(op.f("ix_vulnerabilities_is_rejected"), "vulnerabilities", ["is_rejected"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_vulnerabilities_is_rejected"), table_name="vulnerabilities")
    op.drop_index(op.f("ix_vulnerabilities_last_modified_at"), table_name="vulnerabilities")
    op.drop_index(op.f("ix_vulnerabilities_published_at"), table_name="vulnerabilities")
    op.drop_index(op.f("ix_vulnerabilities_cvss_severity"), table_name="vulnerabilities")
    op.drop_index(op.f("ix_vulnerabilities_source"), table_name="vulnerabilities")
    op.drop_index(op.f("ix_vulnerabilities_cve_id"), table_name="vulnerabilities")
    op.drop_table("vulnerabilities")
