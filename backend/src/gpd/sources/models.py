from datetime import datetime, timezone
import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

try:
    from gpd.db.models import Base, new_uuid, utc_now_iso
except ImportError:
    def utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def new_uuid() -> str:
        return str(uuid.uuid4())

    class Base(DeclarativeBase):  # type: ignore[no-redef]
        pass


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("project_id", "content_hash", "type", name="uq_sources_project_hash_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_ref: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    captured_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)

    spans: Mapped[list["SourceSpan"]] = relationship(
        "SourceSpan", back_populates="source", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        "KnowledgeChunk", back_populates="source", cascade="all, delete-orphan"
    )


class SourceSpan(Base):
    __tablename__ = "source_spans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    locator: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)

    source: Mapped["Source"] = relationship("Source", back_populates="spans")


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="confirmed", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    valid_from: Mapped[str | None] = mapped_column(Text, nullable=True)
    valid_until: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)

    evidence: Mapped[list["KnowledgeEvidence"]] = relationship(
        "KnowledgeEvidence", back_populates="knowledge_item", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        "KnowledgeChunk", back_populates="knowledge_item", cascade="all, delete-orphan"
    )


class KnowledgeEvidence(Base):
    __tablename__ = "knowledge_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    knowledge_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False
    )
    source_span_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("source_spans.id", ondelete="SET NULL"), nullable=True
    )
    source_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=True
    )
    support_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)

    knowledge_item: Mapped["KnowledgeItem"] = relationship(
        "KnowledgeItem", back_populates="evidence"
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=True
    )
    knowledge_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=True
    )
    locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)

    source: Mapped["Source | None"] = relationship("Source", back_populates="chunks")
    knowledge_item: Mapped["KnowledgeItem | None"] = relationship(
        "KnowledgeItem", back_populates="chunks"
    )
