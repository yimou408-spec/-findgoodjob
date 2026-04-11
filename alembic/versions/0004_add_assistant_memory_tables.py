"""add assistant memory tables

Revision ID: 0004_add_assistant_memory_tables
Revises: 0003_remove_job_source
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_add_assistant_memory_tables"
down_revision = "0003_remove_job_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_threads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("workspace_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["job_descriptions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_assistant_threads_id"), "assistant_threads", ["id"], unique=False)
    op.create_index(op.f("ix_assistant_threads_job_id"), "assistant_threads", ["job_id"], unique=True)

    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["thread_id"], ["assistant_threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_assistant_messages_id"), "assistant_messages", ["id"], unique=False)
    op.create_index(op.f("ix_assistant_messages_thread_id"), "assistant_messages", ["thread_id"], unique=False)

    op.create_table(
        "resume_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("source_resume_text", sa.Text(), nullable=False),
        sa.Column("revised_resume", sa.Text(), nullable=False),
        sa.Column("match_score", sa.Integer(), nullable=True),
        sa.Column("match_explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["job_descriptions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resume_revisions_id"), "resume_revisions", ["id"], unique=False)
    op.create_index(op.f("ix_resume_revisions_job_id"), "resume_revisions", ["job_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_resume_revisions_job_id"), table_name="resume_revisions")
    op.drop_index(op.f("ix_resume_revisions_id"), table_name="resume_revisions")
    op.drop_table("resume_revisions")

    op.drop_index(op.f("ix_assistant_messages_thread_id"), table_name="assistant_messages")
    op.drop_index(op.f("ix_assistant_messages_id"), table_name="assistant_messages")
    op.drop_table("assistant_messages")

    op.drop_index(op.f("ix_assistant_threads_job_id"), table_name="assistant_threads")
    op.drop_index(op.f("ix_assistant_threads_id"), table_name="assistant_threads")
    op.drop_table("assistant_threads")
