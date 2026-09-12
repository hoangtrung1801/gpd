from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any, Generator
import pytest

# Ensure backend/src from both worktrees are in sys.path
our_src = Path(__file__).resolve().parents[2] / "src"
if str(our_src) not in sys.path:
    sys.path.insert(0, str(our_src))

foundation_src = Path("/home/work/gpd-worktrees/foundation/backend/src")
if foundation_src.exists() and str(foundation_src) not in sys.path:
    sys.path.append(str(foundation_src))

try:
    import gpd
    our_gpd = our_src / "gpd"
    if our_gpd.exists() and str(our_gpd) not in gpd.__path__:
        gpd.__path__.append(str(our_gpd))
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.testclient import TestClient
from alembic.config import Config
from alembic import command
from sqlalchemy import text

from gpd.app import create_app
from gpd.db.engine import Database
from gpd.knowledge.embeddings import MockEmbeddingProvider
from gpd.knowledge.search import (
    HybridSearchService,
    IndexedChunk,
    RankedChunk,
    SqliteSearchIndex,
)
from gpd.settings import Settings
import gpd.app
import gpd.db.migrations


def run_all_migrations(database: Database, *args, **kwargs) -> None:
    from gpd.db.migrations import run_migrations
    run_migrations(database)


@pytest.fixture
def database(tmp_path: Path) -> Generator[Database, None, None]:
    db_file = tmp_path / "test_knowledge.db"
    db = Database.open(db_file)
    run_all_migrations(db)

    # Seed test project
    with db.session() as session:
        session.execute(
            text("""
                INSERT OR IGNORE INTO projects(id, name, team_identifier, created_at)
                VALUES ('p1', 'Test Project P1', 'team-1', '2026-09-12T00:00:00Z'),
                       ('p2', 'Test Project P2', 'team-2', '2026-09-12T00:00:00Z');
            """)
        )
        session.commit()

    yield db
    db.close()


@pytest.fixture
def search_index(database: Database) -> SqliteSearchIndex:
    return SqliteSearchIndex(database.session, vector_enabled=True)


@pytest.fixture
def embedding_provider() -> MockEmbeddingProvider:
    return MockEmbeddingProvider(dimension=384)


class MockDirectRelationshipProvider:
    def get_direct_chunks(
        self, project_id: str, task_id: str | None, files: list[str]
    ) -> list[RankedChunk]:
        results = []
        if task_id == "task-1":
            results.append(
                RankedChunk(
                    chunk_id="directly-linked",
                    score=0.5,
                    text="Chunk directly linked to task-1",
                    metadata={
                        "linked_task_ids": ["task-1"],
                        "related_files": ["src/payment/service.ts"],
                        "component": "payment",
                    },
                )
            )
        return results


@pytest.fixture
def direct_relationships() -> MockDirectRelationshipProvider:
    return MockDirectRelationshipProvider()


@pytest.fixture
def hybrid_search(
    search_index: SqliteSearchIndex,
    embedding_provider: MockEmbeddingProvider,
    direct_relationships: MockDirectRelationshipProvider,
    database: Database,
) -> HybridSearchService:
    # Seed knowledge chunks for search
    with database.session() as session:
        session.execute(
            text("""
                INSERT OR IGNORE INTO knowledge_chunks(id, project_id, chunk_text, token_estimate, metadata_json, created_at)
                VALUES
                ('directly-linked', 'p1', 'expired payment method resolution guide', 10,
                 '{"linked_task_ids": ["task-1"], "related_files": ["src/payment/service.ts"]}', '2026-09-12T00:00:00Z'),
                ('payment-chunk', 'p1', 'general payment processing details', 8,
                 '{"related_files": ["src/payment/service.ts"], "component": "payment"}', '2026-09-12T00:00:00Z'),
                ('other-chunk', 'p1', 'unrelated inventory sync', 5,
                 '{}', '2026-09-12T00:00:00Z'),
                ('p2-chunk', 'p2', 'expired payment method in other project', 10,
                 '{}', '2026-09-12T00:00:00Z');
            """)
        )
        session.commit()

    return HybridSearchService(
        search_index=search_index,
        embedding_provider=embedding_provider,
        direct_relationship_provider=direct_relationships,
    )


@pytest.fixture
def search_without_vec(
    database: Database,
    direct_relationships: MockDirectRelationshipProvider,
) -> HybridSearchService:
    index = SqliteSearchIndex(database.session, vector_enabled=False)
    with database.session() as session:
        session.execute(
            text("""
                INSERT OR IGNORE INTO knowledge_chunks(id, project_id, chunk_text, token_estimate, metadata_json, created_at)
                VALUES
                ('chunk-no-vec', 'p1', 'payment invalid card number error', 10, '{}', '2026-09-12T00:00:00Z');
            """)
        )
        session.commit()
    return HybridSearchService(
        search_index=index,
        embedding_provider=None,
        direct_relationship_provider=direct_relationships,
    )


@pytest.fixture
def search_without_any_index(
    database: Database,
    direct_relationships: MockDirectRelationshipProvider,
) -> HybridSearchService:
    index = SqliteSearchIndex(database.session, vector_enabled=False)
    index.set_lexical_enabled(False)
    return HybridSearchService(
        search_index=index,
        embedding_provider=None,
        direct_relationship_provider=direct_relationships,
    )


@pytest.fixture
def app(database: Database, tmp_path: Path) -> FastAPI:
    settings = Settings(
        database_path=tmp_path / "test_knowledge.db",
        api_host="127.0.0.1",
        api_port=7337,
        app_version="0.1.0",
    )
    application = create_app(settings)
    application.state.database = database
    return application


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
