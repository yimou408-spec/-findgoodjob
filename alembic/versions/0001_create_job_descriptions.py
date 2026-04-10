"""create job descriptions table"""

from alembic import op
import sqlalchemy as sa


revision = "0001_create_job_descriptions"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_descriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("jd_text", sa.Text(), nullable=False),
        sa.Column("analysis_result", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="created"),
        sa.Column("analysis_model", sa.String(length=100), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_job_descriptions_id", "job_descriptions", ["id"])
    op.create_index("ix_job_descriptions_title", "job_descriptions", ["title"])
    op.create_index("ix_job_descriptions_company", "job_descriptions", ["company"])


def downgrade() -> None:
    op.drop_index("ix_job_descriptions_company", table_name="job_descriptions")
    op.drop_index("ix_job_descriptions_title", table_name="job_descriptions")
    op.drop_index("ix_job_descriptions_id", table_name="job_descriptions")
    op.drop_table("job_descriptions")
