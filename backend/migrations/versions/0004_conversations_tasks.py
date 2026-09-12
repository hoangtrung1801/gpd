"""create conversations, messages, tasks, bug_details, task_sources, task_knowledge, task_files, llm_runs, and public_id_counters tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("channel_id", sa.String(length=255), nullable=False),
        sa.Column("thread_ts", sa.String(length=255), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_id", "thread_ts", name="uq_conversations_channel_thread"),
    )

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("external_message_id", sa.String(length=255), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.Text(), nullable=False),
        sa.Column("ordering", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            "external_message_id",
            name="uq_conversation_messages_external",
        ),
    )

    op.create_table(
        "public_id_counters",
        sa.Column("prefix", sa.String(length=32), nullable=False),
        sa.Column("last_value", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("prefix"),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("public_id", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("type", sa.String(length=64), server_default="bug", nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=64), server_default="open", nullable=False),
        sa.Column("priority", sa.String(length=64), server_default="medium", nullable=False),
        sa.Column("reporter", sa.String(length=255), nullable=True),
        sa.Column("assignee", sa.String(length=255), nullable=True),
        sa.Column("component", sa.String(length=255), nullable=True),
        sa.Column("acceptance_criteria", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_tasks_public_id"),
    )

    op.create_table(
        "bug_details",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("reproduction_steps", sa.Text(), nullable=True),
        sa.Column("actual_behavior", sa.Text(), nullable=True),
        sa.Column("expected_behavior", sa.Text(), nullable=True),
        sa.Column("environment", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=64), nullable=True),
        sa.Column("affected_component", sa.String(length=255), nullable=True),
        sa.Column("technical_clues", sa.Text(), nullable=True),
        sa.Column("participants", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uq_bug_details_task_id"),
    )

    op.create_table(
        "task_sources",
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("relationship", sa.String(length=64), server_default="source", nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "source_id"),
    )

    op.create_table(
        "task_knowledge",
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_id", sa.String(length=36), nullable=False),
        sa.Column("relationship", sa.String(length=64), server_default="context", nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "knowledge_id"),
    )

    op.create_table(
        "task_files",
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "file_path"),
    )

    op.create_table(
        "llm_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workflow", sa.String(length=120), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("source_references", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("validation_errors", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("llm_runs")
    op.drop_table("task_files")
    op.drop_table("task_knowledge")
    op.drop_table("task_sources")
    op.drop_table("bug_details")
    op.drop_table("tasks")
    op.drop_table("public_id_counters")
    op.drop_table("conversation_messages")
    op.drop_table("conversations")
