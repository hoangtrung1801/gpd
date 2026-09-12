import pytest
from sqlalchemy import text
from gpd.db.engine import Database
from gpd.knowledge.search import SqliteSearchIndex


def test_fts_triggers_insert_sync(database: Database, search_index: SqliteSearchIndex):
    """Test that inserting into knowledge_chunks automatically syncs to knowledge_chunks_fts via trigger."""
    with database.session() as session:
        session.execute(
            text("""
                INSERT INTO knowledge_chunks(id, project_id, chunk_text, token_estimate, created_at)
                VALUES ('c-insert-1', 'p1', 'Postgres connection pool exhaustion failure', 12, '2026-09-12T00:00:00Z');
            """)
        )
        session.commit()

    hits = search_index.lexical(project_id="p1", query="exhaustion failure", limit=10)
    assert len(hits) >= 1
    assert any(h.chunk_id == "c-insert-1" for h in hits)
    assert "exhaustion" in hits[0].text


def test_fts_triggers_update_sync(database: Database, search_index: SqliteSearchIndex):
    """Test that updating knowledge_chunks syncs delete+insert to knowledge_chunks_fts."""
    with database.session() as session:
        session.execute(
            text("""
                INSERT INTO knowledge_chunks(id, project_id, chunk_text, token_estimate, created_at)
                VALUES ('c-update-1', 'p1', 'alpha term unique text', 8, '2026-09-12T00:00:00Z');
            """)
        )
        session.commit()

    # Alpha matches
    assert len(search_index.lexical(project_id="p1", query="alpha", limit=5)) == 1

    # Update to beta
    with database.session() as session:
        session.execute(
            text("""
                UPDATE knowledge_chunks
                SET chunk_text = 'beta term replaced text'
                WHERE id = 'c-update-1';
            """)
        )
        session.commit()

    # Alpha no longer matches, beta matches
    assert len(search_index.lexical(project_id="p1", query="alpha", limit=5)) == 0
    beta_hits = search_index.lexical(project_id="p1", query="beta", limit=5)
    assert len(beta_hits) == 1
    assert beta_hits[0].chunk_id == "c-update-1"


def test_fts_triggers_delete_sync(database: Database, search_index: SqliteSearchIndex):
    """Test that deleting from knowledge_chunks removes from knowledge_chunks_fts."""
    with database.session() as session:
        session.execute(
            text("""
                INSERT INTO knowledge_chunks(id, project_id, chunk_text, token_estimate, created_at)
                VALUES ('c-delete-1', 'p1', 'transient ephemeral content', 6, '2026-09-12T00:00:00Z');
            """)
        )
        session.commit()

    assert len(search_index.lexical(project_id="p1", query="transient", limit=5)) == 1

    with database.session() as session:
        session.execute(
            text("DELETE FROM knowledge_chunks WHERE id = 'c-delete-1'")
        )
        session.commit()

    assert len(search_index.lexical(project_id="p1", query="transient", limit=5)) == 0


def test_fts_project_scoped_search(database: Database, search_index: SqliteSearchIndex):
    """Test that lexical search filters strictly by project_id."""
    with database.session() as session:
        session.execute(
            text("""
                INSERT INTO knowledge_chunks(id, project_id, chunk_text, token_estimate, created_at)
                VALUES ('p1-unique', 'p1', 'common project keyword shared', 10, '2026-09-12T00:00:00Z'),
                       ('p2-unique', 'p2', 'common project keyword shared', 10, '2026-09-12T00:00:00Z');
            """)
        )
        session.commit()

    p1_hits = search_index.lexical(project_id="p1", query="common project keyword", limit=10)
    assert len(p1_hits) == 1
    assert p1_hits[0].chunk_id == "p1-unique"

    p2_hits = search_index.lexical(project_id="p2", query="common project keyword", limit=10)
    assert len(p2_hits) == 1
    assert p2_hits[0].chunk_id == "p2-unique"


def test_fts_bm25_ranking(database: Database, search_index: SqliteSearchIndex):
    """Test that lexical hits are ranked by relevance."""
    with database.session() as session:
        session.execute(
            text("""
                INSERT INTO knowledge_chunks(id, project_id, chunk_text, token_estimate, created_at)
                VALUES
                ('exact-hit', 'p1', 'database connection timeout during peak hours', 10, '2026-09-12T00:00:00Z'),
                ('partial-hit', 'p1', 'database configuration guide for local setup', 10, '2026-09-12T00:00:00Z');
            """)
        )
        session.commit()

    hits = search_index.lexical(project_id="p1", query="connection timeout", limit=5)
    assert len(hits) >= 1
    assert hits[0].chunk_id == "exact-hit"
