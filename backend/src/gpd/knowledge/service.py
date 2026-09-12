from datetime import datetime, timezone
from typing import Any, Sequence
import uuid
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Float, ForeignKey, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

from gpd.audit.service import append as append_audit
from gpd.db.engine import Database
from gpd.db.models import Base


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_uuid() -> str:
    return str(uuid.uuid4())


class KnowledgeEvidenceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    knowledge_id: str
    evidence_type: str
    target_id: str
    detail: str | None = None
    created_at: str


class KnowledgeItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    type: str
    title: str
    content: str
    confidence: float = 1.0
    status: str = "confirmed"  # confirmed, superseded, pending, rejected
    evidence: list[KnowledgeEvidenceSchema] = Field(default_factory=list)
    created_at: str
    updated_at: str


class KnowledgeItemModel(Base):
    __tablename__ = "knowledge_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="confirmed", nullable=False)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)

    evidence: Mapped[list["KnowledgeEvidenceModel"]] = relationship(
        "KnowledgeEvidenceModel", back_populates="knowledge_item", cascade="all, delete-orphan"
    )

    def to_schema(self) -> KnowledgeItem:
        return KnowledgeItem(
            id=self.id,
            project_id=self.project_id,
            type=self.type,
            title=self.title,
            content=self.content,
            confidence=self.confidence,
            status=self.status,
            evidence=[e.to_schema() for e in self.evidence],
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class KnowledgeEvidenceModel(Base):
    __tablename__ = "knowledge_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    knowledge_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_items.id", ondelete="CASCADE"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)

    knowledge_item: Mapped["KnowledgeItemModel"] = relationship(
        "KnowledgeItemModel", back_populates="evidence"
    )

    def to_schema(self) -> KnowledgeEvidenceSchema:
        return KnowledgeEvidenceSchema(
            id=self.id,
            knowledge_id=self.knowledge_id,
            evidence_type=self.evidence_type,
            target_id=self.target_id,
            detail=self.detail,
            created_at=self.created_at,
        )


class KnowledgeService:
    def __init__(self, database: Database):
        self.database = database

    def create_confirmed_item(
        self,
        project_id: str,
        type: str,
        title: str,
        content: str,
        evidence: Sequence[dict[str, Any]] | None = None,
        confidence: float = 1.0,
    ) -> KnowledgeItem:
        def _txn() -> KnowledgeItem:
            with self.database.session() as session:
                with session.begin():
                    now = utc_now_iso()
                    item = KnowledgeItemModel(
                        id=new_uuid(),
                        project_id=project_id,
                        type=type,
                        title=title,
                        content=content,
                        confidence=confidence,
                        status="confirmed",
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(item)
                    session.flush()

                    if evidence:
                        for ev in evidence:
                            session.add(
                                KnowledgeEvidenceModel(
                                    id=new_uuid(),
                                    knowledge_id=item.id,
                                    evidence_type=ev.get("evidence_type", "reference"),
                                    target_id=ev.get("target_id", ""),
                                    detail=ev.get("detail"),
                                    created_at=now,
                                )
                            )
                    session.flush()
                    return item.to_schema()

        # Database.write is async, but this is a synchronous helper for test/internal use
        # Let's support both sync execution via database.session() directly or asyncio.to_thread
        return _txn()

    def get_item(self, item_id: str) -> KnowledgeItem | None:
        with self.database.session() as session:
            model = session.execute(
                select(KnowledgeItemModel).where(KnowledgeItemModel.id == item_id)
            ).scalar_one_or_none()
            return model.to_schema() if model else None

    def list_items(
        self, project_id: str, status: str | None = "confirmed"
    ) -> list[KnowledgeItem]:
        with self.database.session() as session:
            stmt = select(KnowledgeItemModel).where(KnowledgeItemModel.project_id == project_id)
            if status:
                stmt = stmt.where(KnowledgeItemModel.status == status)
            models = session.execute(stmt.order_by(KnowledgeItemModel.created_at.desc())).scalars().all()
            return [m.to_schema() for m in models]

    def supersede(self, loser_id: str, winner_id: str) -> None:
        with self.database.session() as session:
            with session.begin():
                model = session.execute(
                    select(KnowledgeItemModel).where(KnowledgeItemModel.id == loser_id)
                ).scalar_one_or_none()
                if model:
                    model.status = "superseded"
                    model.updated_at = utc_now_iso()
                session.flush()
