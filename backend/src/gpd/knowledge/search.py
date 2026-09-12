from collections.abc import Sequence
from dataclasses import dataclass, field
import json
import logging
from typing import Any, Protocol

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from gpd.knowledge.embeddings import EmbeddingProvider
from gpd.knowledge.scoring import (
    apply_boosts_and_penalties,
    reciprocal_rank_fusion,
)

logger = logging.getLogger(__name__)


@dataclass
class IndexedChunk:
    chunk_id: str
    project_id: str
    text: str
    source_id: str | None = None
    knowledge_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: Sequence[float] | None = None


@dataclass
class RankedChunk:
    chunk_id: str
    score: float
    lexical_score: float = 0.0
    vector_score: float = 0.0
    selection_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    text: str = ""


@dataclass
class SearchHealth:
    lexical_available: bool = True
    vector_available: bool = True
    error: str | None = None


class SearchIndex(Protocol):
    def index_chunks(self, chunks: Sequence[IndexedChunk]) -> None: ...
    def lexical(self, project_id: str, query: str, limit: int) -> list[RankedChunk]: ...
    def vector(self, project_id: str, vector: Sequence[float], limit: int) -> list[RankedChunk]: ...
    def health(self) -> SearchHealth: ...


class SqliteSearchIndex:
    """Search index implementation backed by SQLite FTS5 and sqlite-vec."""

    def __init__(self, session_factory, vector_enabled: bool = True):
        self.session_factory = session_factory
        self._vector_enabled = vector_enabled
        self._lexical_enabled = True

    def health(self) -> SearchHealth:
        lexical_ok = self._lexical_enabled
        vector_ok = self._vector_enabled

        with self.session_factory() as session:
            if lexical_ok:
                try:
                    session.execute(text("SELECT 1 FROM knowledge_chunks_fts LIMIT 0"))
                except Exception:
                    lexical_ok = False

            if vector_ok:
                try:
                    session.execute(text("SELECT 1 FROM knowledge_chunks_vec LIMIT 0"))
                except Exception:
                    vector_ok = False

        return SearchHealth(lexical_available=lexical_ok, vector_available=vector_ok)

    def set_lexical_enabled(self, enabled: bool) -> None:
        self._lexical_enabled = enabled

    def set_vector_enabled(self, enabled: bool) -> None:
        self._vector_enabled = enabled

    def index_chunks(self, chunks: Sequence[IndexedChunk]) -> None:
        with self.session_factory() as session:
            for chunk in chunks:
                if chunk.embedding and self._vector_enabled:
                    try:
                        import sqlite_vec
                        serialized = sqlite_vec.serialize_float32(list(chunk.embedding))
                        session.execute(
                            text("""
                                INSERT OR REPLACE INTO knowledge_chunks_vec(chunk_id, embedding)
                                VALUES (:chunk_id, :embedding)
                            """),
                            {"chunk_id": chunk.chunk_id, "embedding": serialized},
                        )
                    except Exception as e:
                        logger.warning(f"Failed to index vector for chunk {chunk.chunk_id}: {e}")
            session.commit()

    def lexical(self, project_id: str, query: str, limit: int = 10) -> list[RankedChunk]:
        if not self._lexical_enabled:
            return []

        clean_query = query.replace('"', '""').strip()
        if not clean_query:
            return []

        match_terms = " ".join(f'"{term}"' for term in clean_query.split() if term)
        if not match_terms:
            return []

        with self.session_factory() as session:
            try:
                sql = text("""
                    SELECT kc.id, kc.chunk_text, kc.metadata_json, bm25(knowledge_chunks_fts) as rank
                    FROM knowledge_chunks_fts fts
                    JOIN knowledge_chunks kc ON kc.rowid = fts.rowid
                    WHERE knowledge_chunks_fts MATCH :match_query AND fts.project_id = :project_id
                    ORDER BY rank ASC
                    LIMIT :limit
                """)
                rows = session.execute(
                    sql,
                    {"match_query": match_terms, "project_id": project_id, "limit": limit},
                ).fetchall()

                results: list[RankedChunk] = []
                for row in rows:
                    meta = json.loads(row.metadata_json) if row.metadata_json else {}
                    score = abs(float(row.rank)) if row.rank is not None else 0.0
                    results.append(
                        RankedChunk(
                            chunk_id=row.id,
                            score=score,
                            lexical_score=score,
                            text=row.chunk_text,
                            metadata=meta,
                        )
                    )
                return results
            except Exception as e:
                logger.warning(f"FTS lexical search failed: {e}")
                return []

    def vector(self, project_id: str, vector: Sequence[float], limit: int = 10) -> list[RankedChunk]:
        if not self._vector_enabled:
            return []

        with self.session_factory() as session:
            try:
                import sqlite_vec
                serialized = sqlite_vec.serialize_float32(list(vector))
                sql = text("""
                    SELECT v.chunk_id, v.distance, kc.chunk_text, kc.metadata_json
                    FROM knowledge_chunks_vec v
                    JOIN knowledge_chunks kc ON kc.id = v.chunk_id
                    WHERE v.embedding MATCH :vector AND k = :limit AND kc.project_id = :project_id
                    ORDER BY v.distance ASC
                """)
                rows = session.execute(
                    sql,
                    {"vector": serialized, "limit": limit, "project_id": project_id},
                ).fetchall()

                results: list[RankedChunk] = []
                for row in rows:
                    dist = float(row.distance) if row.distance is not None else 1.0
                    score = max(0.0, 1.0 - dist)
                    meta = json.loads(row.metadata_json) if row.metadata_json else {}
                    results.append(
                        RankedChunk(
                            chunk_id=row.chunk_id,
                            score=score,
                            vector_score=score,
                            text=row.chunk_text,
                            metadata=meta,
                        )
                    )
                return results
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")
                return []


@dataclass
class SearchQuery:
    project_id: str
    text: str
    task_id: str | None = None
    related_files: list[str] = field(default_factory=list)
    component: str | None = None
    limit: int = 10


@dataclass
class SearchResult:
    hits: list[RankedChunk] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class HybridSearchService:
    """Deterministic hybrid search with RRF fusion, relationship boosts, and degraded modes."""

    def __init__(
        self,
        search_index: SearchIndex,
        embedding_provider: EmbeddingProvider | None = None,
        direct_relationship_provider: Any = None,
    ):
        self.search_index = search_index
        self.embedding_provider = embedding_provider
        self.direct_relationship_provider = direct_relationship_provider

    def search(self, query: SearchQuery) -> SearchResult:
        warnings: list[str] = []
        health = self.search_index.health()

        lexical_ok = health.lexical_available
        vector_ok = health.vector_available and self.embedding_provider is not None
        if not lexical_ok:
            warnings.append("lexical_search_unavailable")
        if not vector_ok:
            warnings.append("vector_search_unavailable")

        lexical_hits: list[RankedChunk] = []
        vector_hits: list[RankedChunk] = []
        chunk_map: dict[str, RankedChunk] = {}

        # 1. Lexical retrieval
        if lexical_ok and query.text:
            lexical_hits = self.search_index.lexical(
                project_id=query.project_id,
                query=query.text,
                limit=query.limit * 2,
            )
            for hit in lexical_hits:
                chunk_map[hit.chunk_id] = hit

        # 2. Vector retrieval
        if vector_ok and query.text and self.embedding_provider is not None:
            try:
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            embeddings = pool.submit(
                                asyncio.run, self.embedding_provider.embed([query.text])
                            ).result()
                    else:
                        embeddings = loop.run_until_complete(
                            self.embedding_provider.embed([query.text])
                        )
                except RuntimeError:
                    embeddings = asyncio.run(self.embedding_provider.embed([query.text]))

                if embeddings and len(embeddings) > 0:
                    vector_hits = self.search_index.vector(
                        project_id=query.project_id,
                        vector=embeddings[0],
                        limit=query.limit * 2,
                    )
                    for hit in vector_hits:
                        if hit.chunk_id in chunk_map:
                            chunk_map[hit.chunk_id].vector_score = hit.vector_score
                        else:
                            chunk_map[hit.chunk_id] = hit
            except Exception as e:
                logger.warning(f"Embedding/vector search failed: {e}")
                if "vector_search_unavailable" not in warnings:
                    warnings.append("vector_search_unavailable")

        # 3. Direct relationships
        direct_chunks: list[RankedChunk] = []
        if self.direct_relationship_provider is not None:
            direct_chunks = self.direct_relationship_provider.get_direct_chunks(
                project_id=query.project_id,
                task_id=query.task_id,
                files=query.related_files,
            )
            for dc in direct_chunks:
                if dc.chunk_id not in chunk_map:
                    chunk_map[dc.chunk_id] = dc

        # 4. Reciprocal Rank Fusion
        rankings = []
        if lexical_hits:
            rankings.append([h.chunk_id for h in lexical_hits])
        if vector_hits:
            rankings.append([h.chunk_id for h in vector_hits])
        if direct_chunks:
            rankings.append([h.chunk_id for h in direct_chunks])

        rrf_scores = reciprocal_rank_fusion(rankings, k=60) if rankings else {}

        # 5. Apply boosts & penalties
        final_hits: list[RankedChunk] = []
        for chunk_id, chunk in chunk_map.items():
            base_score = rrf_scores.get(chunk_id, 0.0)
            boosted_score, reasons = apply_boosts_and_penalties(
                base_score=base_score,
                metadata=chunk.metadata,
                query_task_id=query.task_id,
                query_files=query.related_files,
                query_component=query.component,
            )
            final_hits.append(
                RankedChunk(
                    chunk_id=chunk_id,
                    score=boosted_score,
                    lexical_score=chunk.lexical_score,
                    vector_score=chunk.vector_score,
                    selection_reasons=reasons,
                    metadata=chunk.metadata,
                    text=chunk.text,
                )
            )

        # 6. Sort by boosted score descending
        final_hits.sort(key=lambda x: x.score, reverse=True)

        # Minimal context package fallback: ensure direct relationships are included if both indexes down
        if not lexical_ok and not vector_ok and direct_chunks and not final_hits:
            final_hits = direct_chunks

        return SearchResult(
            hits=final_hits[: query.limit],
            warnings=warnings,
        )
