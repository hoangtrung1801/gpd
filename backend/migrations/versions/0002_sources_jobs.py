"""create sources, source_spans, knowledge_items, knowledge_evidence, knowledge_chunks, jobs, and job_attempts

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-12 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. sources
    op.create_table(
        "sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("canonical_ref", sa.String(length=1024), nullable=True),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("captured_at", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "content_hash", "type", name="uq_sources_project_hash_type"),
        sa.CheckConstraint(
            "state IN ('queued', 'parsing', 'indexing', 'ready', 'embedding_pending', 'failed')",
            name="ck_sources_state",
        ),
    )

    # 2. source_spans
    op.create_table(
        "source_spans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("locator", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 3. knowledge_items
    op.create_table(
        "knowledge_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="confirmed", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("valid_from", sa.Text(), nullable=True),
        sa.Column("valid_until", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('confirmed', 'superseded', 'deprecated', 'unconfirmed')",
            name="ck_knowledge_items_status",
        ),
    )

    # 4. knowledge_evidence
    op.create_table(
        "knowledge_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_id", sa.String(length=36), nullable=False),
        sa.Column("source_span_id", sa.String(length=36), nullable=True),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("support_type", sa.String(length=64), nullable=True),
        sa.Column("evidence_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.Text(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["knowledge_id"], ["knowledge_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_span_id"], ["source_spans.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 5. knowledge_chunks
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("knowledge_id", sa.String(length=36), nullable=True),
        sa.Column("locator", sa.String(length=255), nullable=True),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), server_default="0", nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_id"], ["knowledge_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 6. jobs
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("progress", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("worker_id", sa.String(length=255), nullable=True),
        sa.Column("lease_expires_at", sa.Text(), nullable=True),
        sa.Column("error_category", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_jobs_idempotency_key"),
        sa.CheckConstraint(
            "state IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_jobs_state",
        ),
    )

    # 7. job_attempts
    op.create_table(
        "job_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=255), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("finished_at", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "state IN ('running', 'succeeded', 'failed')",
            name="ck_job_attempts_state",
        ),
    )


def downgrade() -> None:
    op.drop_table("job_attempts")
    op.drop_table("jobs")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_evidence")
    op.drop_table("knowledge_items")
    op.drop_table("source_spans")
    op.drop_table("sources")
