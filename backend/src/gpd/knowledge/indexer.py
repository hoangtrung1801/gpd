import hashlib
import json
import logging
from typing import Sequence
from sqlalchemy import select, text

from gpd.db.engine import Database
from gpd.knowledge.embeddings import EmbeddingProvider, validate_embedding
from gpd.sources.models import KnowledgeChunk, Source, utc_now_iso
from gpd.sources.parsers import parse_markdown
from gpd.sources.repository import SourceRepository

logger = logging.getLogger(__name__)


class KnowledgeIndexer:
    def __init__(
        self,
        database: Database,
        embedding_provider: EmbeddingProvider | None = None,
        provider_name: str = "mock",
        model_name: str = "mock-embed-v1",
    ):
        self.database = database
        self.embedding_provider = embedding_provider
        self.provider_name = provider_name
        self.model_name = model_name

    async def index_source(self, source_id: str) -> str:
        """Parse source into chunks, save to database (triggering FTS5), and embed asynchronously."""
        # 1. Fetch raw source content
        def _get_source():
            with self.database.session() as session:
                repo = SourceRepository(session)
                source = repo.get_by_id(source_id)
                if source is None:
                    return None
                repo.update_state(source_id, "parsing")
                session.commit()
                return {
                    "id": source.id,
                    "project_id": source.project_id,
                    "raw_content": source.raw_content,
                    "type": source.type,
                }

        source_info = await self.database.write(_get_source)
        if source_info is None:
            return "not_found"

        project_id = source_info["project_id"]
        raw_content = source_info["raw_content"]

        # 2. Parse markdown into chunks (CPU work outside DB transaction)
        try:
            chunks = parse_markdown(raw_content)
        except Exception as e:
            def _fail_parse():
                with self.database.session() as session:
                    repo = SourceRepository(session)
                    repo.update_state(source_id, "failed", error_message=f"Markdown parsing error: {e}")
                    session.commit()

            await self.database.write(_fail_parse)
            return "failed"

        # 3. Save spans and chunks in DB (triggers FTS5 automatically via triggers)
        def _save_chunks():
            with self.database.session() as session:
                repo = SourceRepository(session)
                repo.update_state(source_id, "indexing")
                spans, saved_chunks = repo.save_spans_and_chunks(source_id, project_id, chunks)
                chunk_data = [(c.id, c.chunk_text) for c in saved_chunks]
                session.commit()
                return chunk_data

        saved_chunk_data = await self.database.write(_save_chunks)

        # 4. Generate embeddings (network/compute outside DB write transaction)
        embeddings: list[list[float]] | None = None
        embedding_failed = False

        if self.embedding_provider is not None and saved_chunk_data:
            texts = [item[1] for item in saved_chunk_data]
            try:
                raw_embeddings = await self.embedding_provider.embed(texts)
                dim = self.embedding_provider.dimension
                embeddings = [validate_embedding(vec, expected_dimension=dim) for vec in raw_embeddings]
            except Exception as e:
                logger.warning(f"Embedding generation failed for source {source_id}: {e}")
                embedding_failed = True

        # 5. Persist vector embeddings and update final source state
        def _save_embeddings():
            with self.database.session() as session:
                repo = SourceRepository(session)
                now_iso = utc_now_iso()

                if embeddings is not None and not embedding_failed:
                    try:
                        import sqlite_vec
                        for (chunk_id, chunk_text_content), vec in zip(saved_chunk_data, embeddings):
                            serialized = sqlite_vec.serialize_float32(vec)
                            session.execute(
                                text("""
                                    INSERT OR REPLACE INTO knowledge_chunks_vec(chunk_id, embedding)
                                    VALUES (:chunk_id, :embedding)
                                """),
                                {"chunk_id": chunk_id, "embedding": serialized},
                            )

                            content_hash = hashlib.sha256(chunk_text_content.encode("utf-8")).hexdigest()
                            session.execute(
                                text("""
                                    INSERT OR REPLACE INTO chunk_embeddings(
                                        chunk_id, provider, model, dimension, content_hash, created_at
                                    ) VALUES (
                                        :chunk_id, :provider, :model, :dimension, :content_hash, :created_at
                                    )
                                """),
                                {
                                    "chunk_id": chunk_id,
                                    "provider": self.provider_name,
                                    "model": self.model_name,
                                    "dimension": self.embedding_provider.dimension if self.embedding_provider else 0,
                                    "content_hash": content_hash,
                                    "created_at": now_iso,
                                },
                            )
                        repo.update_state(source_id, "ready")
                        session.commit()
                        return "ready"
                    except Exception as e:
                        logger.warning(f"Failed to store vectors for source {source_id}: {e}")
                        repo.update_state(source_id, "embedding_pending", error_message=str(e))
                        session.commit()
                        return "embedding_pending"
                else:
                    final_state = "embedding_pending" if (self.embedding_provider is not None or embedding_failed) else "ready"
                    repo.update_state(source_id, final_state)
                    session.commit()
                    return final_state

        return await self.database.write(_save_embeddings)
