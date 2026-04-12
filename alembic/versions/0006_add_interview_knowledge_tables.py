"""add interview knowledge tables

Revision ID: 0006_add_interview_knowledge_tables
Revises: 0005_add_knowledge_base_tables
Create Date: 2026-04-12
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_add_interview_knowledge_tables"
down_revision = "0005_add_knowledge_base_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_chunks", sa.Column("embedding_vector", sa.Text(), nullable=True))

    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_platform", sa.String(length=50), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_id", sa.String(length=120), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("author_name", sa.String(length=255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("crawl_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingest_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=255), nullable=True),
        sa.Column("interview_stage", sa.String(length=50), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("tags_json", sa.Text(), nullable=True),
        sa.Column("quality_score", sa.Integer(), nullable=True),
        sa.Column("compliance_status", sa.String(length=50), nullable=False),
        sa.Column("content_raw", sa.Text(), nullable=False),
        sa.Column("content_clean", sa.Text(), nullable=False),
        sa.Column("content_summary", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_knowledge_sources_id"), "knowledge_sources", ["id"], unique=False)
    op.create_index(op.f("ix_knowledge_sources_source_platform"), "knowledge_sources", ["source_platform"], unique=False)
    op.create_index(op.f("ix_knowledge_sources_source_type"), "knowledge_sources", ["source_type"], unique=False)
    op.create_index(op.f("ix_knowledge_sources_source_id"), "knowledge_sources", ["source_id"], unique=False)
    op.create_index(op.f("ix_knowledge_sources_company"), "knowledge_sources", ["company"], unique=False)
    op.create_index(op.f("ix_knowledge_sources_role"), "knowledge_sources", ["role"], unique=False)
    op.create_index(op.f("ix_knowledge_sources_interview_stage"), "knowledge_sources", ["interview_stage"], unique=False)
    op.create_index(op.f("ix_knowledge_sources_city"), "knowledge_sources", ["city"], unique=False)
    op.create_index(op.f("ix_knowledge_sources_compliance_status"), "knowledge_sources", ["compliance_status"], unique=False)

    op.create_table(
        "retrieval_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("source_platform", sa.String(length=50), nullable=False),
        sa.Column("filters_json", sa.Text(), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_retrieval_logs_id"), "retrieval_logs", ["id"], unique=False)
    op.create_index(op.f("ix_retrieval_logs_source_platform"), "retrieval_logs", ["source_platform"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_retrieval_logs_source_platform"), table_name="retrieval_logs")
    op.drop_index(op.f("ix_retrieval_logs_id"), table_name="retrieval_logs")
    op.drop_table("retrieval_logs")

    op.drop_index(op.f("ix_knowledge_sources_compliance_status"), table_name="knowledge_sources")
    op.drop_index(op.f("ix_knowledge_sources_city"), table_name="knowledge_sources")
    op.drop_index(op.f("ix_knowledge_sources_interview_stage"), table_name="knowledge_sources")
    op.drop_index(op.f("ix_knowledge_sources_role"), table_name="knowledge_sources")
    op.drop_index(op.f("ix_knowledge_sources_company"), table_name="knowledge_sources")
    op.drop_index(op.f("ix_knowledge_sources_source_id"), table_name="knowledge_sources")
    op.drop_index(op.f("ix_knowledge_sources_source_type"), table_name="knowledge_sources")
    op.drop_index(op.f("ix_knowledge_sources_source_platform"), table_name="knowledge_sources")
    op.drop_index(op.f("ix_knowledge_sources_id"), table_name="knowledge_sources")
    op.drop_table("knowledge_sources")

    op.drop_column("knowledge_chunks", "embedding_vector")
