from datetime import datetime, timezone
import json
from typing import Any
import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

from gpd.db.models import Base
from gpd.context.schemas import ContextEntry, ContextPackage


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_uuid() -> str:
    return str(uuid.uuid4())


class ContextPackageModel(Base):
    __tablename__ = "context_packages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    developer_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    renderer_version: Mapped[str] = mapped_column(String(50), default="1.0", nullable=False)
    search_health_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    warning_codes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)

    entries: Mapped[list["ContextEntryModel"]] = relationship(
        "ContextEntryModel", back_populates="package", cascade="all, delete-orphan", order_by="ContextEntryModel.rank"
    )

    def to_schema(self) -> ContextPackage:
        warnings = json.loads(self.warning_codes) if self.warning_codes else []
        search_health = json.loads(self.search_health_snapshot) if self.search_health_snapshot else None
        return ContextPackage(
            id=self.id,
            session_id=self.session_id,
            task_id=self.task_id,
            developer_query=self.developer_query,
            token_budget=self.token_budget,
            estimated_tokens=self.estimated_tokens,
            renderer_version=self.renderer_version,
            search_health_snapshot=search_health,
            warnings=warnings,
            entries=[e.to_schema() for e in self.entries],
            created_at=self.created_at,
        )


class ContextEntryModel(Base):
    __tablename__ = "context_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    package_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("context_packages.id", ondelete="CASCADE"), nullable=False
    )
    section: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    knowledge_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_components: Mapped[str | None] = mapped_column(Text, nullable=True)
    selection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)

    package: Mapped["ContextPackageModel"] = relationship("ContextPackageModel", back_populates="entries")

    def to_schema(self) -> ContextEntry:
        components = json.loads(self.score_components) if self.score_components else None
        return ContextEntry(
            id=self.id,
            section=self.section,
            content=self.content,
            source_id=self.source_id,
            knowledge_id=self.knowledge_id,
            score=self.score,
            score_components=components,
            selection_reason=self.selection_reason,
            rank=self.rank,
            token_estimate=self.token_estimate,
        )


class ContextRepository:
    def save_package(self, session: Session, package: ContextPackage) -> ContextPackageModel:
        model = ContextPackageModel(
            id=package.id,
            session_id=package.session_id,
            task_id=package.task_id,
            developer_query=package.developer_query,
            token_budget=package.token_budget,
            estimated_tokens=package.estimated_tokens,
            renderer_version=package.renderer_version,
            search_health_snapshot=json.dumps(package.search_health_snapshot) if package.search_health_snapshot else None,
            warning_codes=json.dumps(package.warnings) if package.warnings else None,
            created_at=package.created_at,
        )
        session.add(model)
        session.flush()

        for entry in package.entries:
            emodel = ContextEntryModel(
                id=entry.id,
                package_id=model.id,
                section=entry.section,
                content=entry.content,
                source_id=entry.source_id,
                knowledge_id=entry.knowledge_id,
                score=entry.score,
                score_components=json.dumps(entry.score_components) if entry.score_components else None,
                selection_reason=entry.selection_reason,
                rank=entry.rank,
                token_estimate=entry.token_estimate,
                created_at=utc_now_iso(),
            )
            session.add(emodel)

        session.flush()
        return model

    def get_by_id(self, session: Session, package_id: str) -> ContextPackageModel | None:
        return session.execute(
            select(ContextPackageModel).where(ContextPackageModel.id == package_id)
        ).scalar_one_or_none()

    def get_latest_for_session(self, session: Session, session_id: str) -> ContextPackageModel | None:
        return session.execute(
            select(ContextPackageModel)
            .where(ContextPackageModel.session_id == session_id)
            .order_by(ContextPackageModel.created_at.desc())
        ).scalars().first()
