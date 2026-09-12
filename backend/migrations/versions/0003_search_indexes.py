"""create FTS5 external-content table, sync triggers, and vec0 virtual table for knowledge chunks

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-12 00:02:00.000000

Runbook Note (Dimension Change Reindex):
When the embedding model or dimension is updated (e.g. from 384 to 1536):
1. Create a new vec0 table or alter table for the new dimension.
2. The chunk_embeddings table tracks (chunk_id, provider, model, dimension, content_hash).
3. The system finds all knowledge_chunks whose content_hash or (model, dimension) differs
   from the current active configuration and enqueues re-embedding background jobs.
4. Old embeddings are replaced atomically per chunk or in bulk reindexing transactions.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Chunk embeddings metadata table (tracks provider, model, dimension, content hash)
    op.create_table(
        "chunk_embeddings",
        sa.Column("chunk_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["knowledge_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chunk_id"),
    )

    # 2. FTS5 external-content virtual table keyed to knowledge_chunks carrying project_id
    op.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts USING fts5(
            chunk_text,
            project_id UNINDEXED,
            content='knowledge_chunks',
            content_rowid='rowid'
        );
        """
    )

    # 3. Standard three-trigger sync (insert, delete using old.rowid, update delete+insert)
    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS knowledge_chunks_ai AFTER INSERT ON knowledge_chunks BEGIN
            INSERT INTO knowledge_chunks_fts(rowid, chunk_text, project_id)
            VALUES (new.rowid, new.chunk_text, new.project_id);
        END;
        """
    )

    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS knowledge_chunks_ad AFTER DELETE ON knowledge_chunks BEGIN
            INSERT INTO knowledge_chunks_fts(knowledge_chunks_fts, rowid, chunk_text, project_id)
            VALUES ('delete', old.rowid, old.chunk_text, old.project_id);
        END;
        """
    )

    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS knowledge_chunks_au AFTER UPDATE ON knowledge_chunks BEGIN
            INSERT INTO knowledge_chunks_fts(knowledge_chunks_fts, rowid, chunk_text, project_id)
            VALUES ('delete', old.rowid, old.chunk_text, old.project_id);
            INSERT INTO knowledge_chunks_fts(rowid, chunk_text, project_id)
            VALUES (new.rowid, new.chunk_text, new.project_id);
        END;
        """
    )

    # 4. vec0 virtual table with float embedding column at configured dimension (default 384)
    # Attempt to load sqlite-vec extension once if available on this connection
    conn = op.get_bind()
    try:
        import sqlite_vec

        raw_conn = getattr(conn.connection, "dbapi_connection", None)
        if raw_conn is not None and hasattr(raw_conn, "enable_load_extension"):
            raw_conn.enable_load_extension(True)
            sqlite_vec.load(raw_conn)
            raw_conn.enable_load_extension(False)
        op.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_vec USING vec0(
                chunk_id text primary key,
                embedding float[384]
            );
            """
        )
    except Exception:
        # Per-connection failure marks vector health unavailable without blocking migration or FTS5
        pass


def downgrade() -> None:
    conn = op.get_bind()
    try:
        op.execute("DROP TABLE IF EXISTS knowledge_chunks_vec;")
    except Exception:
        pass

    op.execute("DROP TRIGGER IF EXISTS knowledge_chunks_au;")
    op.execute("DROP TRIGGER IF EXISTS knowledge_chunks_ad;")
    op.execute("DROP TRIGGER IF EXISTS knowledge_chunks_ai;")
    op.execute("DROP TABLE IF EXISTS knowledge_chunks_fts;")
    op.drop_table("chunk_embeddings")
