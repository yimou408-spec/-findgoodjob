"""add structured analysis fields

Revision ID: 0002_add_structured_analysis_fields
Revises: 0001_create_job_descriptions
Create Date: 2026-04-11
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_add_structured_analysis_fields"
down_revision = "0001_create_job_descriptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("job_descriptions", sa.Column("analysis_match_score", sa.Integer(), nullable=True))
    op.add_column("job_descriptions", sa.Column("analysis_improvement_advice", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("job_descriptions", "analysis_improvement_advice")
    op.drop_column("job_descriptions", "analysis_match_score")
