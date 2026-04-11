"""remove job source column

Revision ID: 0003_remove_job_source
Revises: 0002_add_structured_analysis_fields
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_remove_job_source"
down_revision = "0002_add_structured_analysis_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("job_descriptions") as batch_op:
        batch_op.drop_column("source")


def downgrade() -> None:
    with op.batch_alter_table("job_descriptions") as batch_op:
        batch_op.add_column(sa.Column("source", sa.String(length=255), nullable=True))
