import hashlib
from typing import Sequence
from sqlalchemy import select, delete
from sqlalchemy.orm import Session, selectinload

from gpd.sources.models import Source, SourceSpan, KnowledgeChunk
from gpd.sources.parsers import ParsedChunk


class SourceRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, source_id: str, with_details: bool = False) -> Source | None:
        stmt = select(Source).where(Source.id == source_id)
        if with_details:
            stmt = stmt.options(selectinload(Source.spans), selectinload(Source.chunks))
        return self.session.execute(stmt).scalar_one_or_none()

    def find_by_content_hash(
        self, project_id: str, content_hash: str, source_type: str
    ) -> Source | None:
        stmt = select(Source).where(
            Source.project_id == project_id,
            Source.content_hash == content_hash,
            Source.type == source_type,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def create(
        self,
        project_id: str,
        source_type: str,
        title: str,
        raw_content: str,
        content_hash: str,
        canonical_ref: str | None = None,
        author: str | None = None,
        captured_at: str | None = None,
    ) -> Source:
        source = Source(
            project_id=project_id,
            type=source_type,
            title=title,
            raw_content=raw_content,
            content_hash=content_hash,
            canonical_ref=canonical_ref,
            author=author,
            captured_at=captured_at,
            state="queued",
        )
        self.session.add(source)
        self.session.flush()
        return source

    def update_state(
        self, source_id: str, state: str, error_message: str | None = None
    ) -> None:
        source = self.get_by_id(source_id)
        if source is not None:
            source.state = state
            source.error_message = error_message
            self.session.flush()

    def save_spans_and_chunks(
        self, source_id: str, project_id: str, chunks: Sequence[ParsedChunk]
    ) -> tuple[list[SourceSpan], list[KnowledgeChunk]]:
        # Re-ingestion replaces derived search rows as DELETE+INSERT in one transaction so triggers fire
        self.session.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.source_id == source_id)
        )
        self.session.execute(
            delete(SourceSpan).where(SourceSpan.source_id == source_id)
        )
        self.session.flush()

        spans: list[SourceSpan] = []
        knowledge_chunks: list[KnowledgeChunk] = []

        for parsed in chunks:
            checksum = hashlib.sha256(parsed.text.encode("utf-8")).hexdigest()
            span = SourceSpan(
                source_id=source_id,
                locator=parsed.locator,
                content=parsed.text,
                checksum=checksum,
            )
            self.session.add(span)
            spans.append(span)

            chunk = KnowledgeChunk(
                project_id=project_id,
                source_id=source_id,
                locator=parsed.locator,
                chunk_text=parsed.text,
                token_estimate=parsed.token_estimate,
            )
            self.session.add(chunk)
            knowledge_chunks.append(chunk)

        self.session.flush()
        return spans, knowledge_chunks

    def list_by_project(
        self, project_id: str, limit: int = 50, cursor: str | None = None
    ) -> list[Source]:
        stmt = select(Source).where(Source.project_id == project_id)
        if cursor is not None:
            stmt = stmt.where(Source.created_at < cursor)
        stmt = stmt.order_by(Source.created_at.desc()).limit(limit)
        return list(self.session.execute(stmt).scalars().all())
