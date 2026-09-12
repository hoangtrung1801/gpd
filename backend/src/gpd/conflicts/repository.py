from datetime import datetime, timezone
from typing import Sequence
import uuid

from sqlalchemy import Float, ForeignKey, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

from gpd.db.models import Base
from gpd.sessions.schemas import ConflictEvidenceSchema


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_uuid() -> str:
    return str(uuid.uuid4())


class ConflictModel(Base):
    __tablename__ = "conflicts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # work_overlap, contradictory_knowledge
    severity: Mapped[str] = mapped_column(String(50), nullable=False)  # high, medium, low
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)  # active, resolved, dismissed
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    detector_version: Mapped[str] = mapped_column(String(50), nullable=False)
    resolution_action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)

    evidence: Mapped[list["ConflictEvidenceModel"]] = relationship(
        "ConflictEvidenceModel", back_populates="conflict", cascade="all, delete-orphan"
    )


class ConflictEvidenceModel(Base):
    __tablename__ = "conflict_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    conflict_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conflicts.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(Text, nullable=False)
    score_component: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)

    conflict: Mapped["ConflictModel"] = relationship("ConflictModel", back_populates="evidence")


class ConflictRepository:
    def create(
        self,
        session: Session,
        project_id: str,
        type: str,
        severity: str,
        explanation: str,
        detector_version: str = "1.0",
        evidence: Sequence[ConflictEvidenceSchema] | None = None,
    ) -> ConflictModel:
        now = utc_now_iso()
        conflict = ConflictModel(
            id=new_uuid(),
            project_id=project_id,
            type=type,
            severity=severity,
            status="active",
            explanation=explanation,
            detector_version=detector_version,
            created_at=now,
            updated_at=now,
        )
        session.add(conflict)
        session.flush()

        if evidence:
            for ev in evidence:
                session.add(
                    ConflictEvidenceModel(
                        id=new_uuid(),
                        conflict_id=conflict.id,
                        kind=ev.kind,
                        target_type=ev.target_type,
                        target_id=ev.target_id,
                        score_component=ev.score_component,
                        detail=ev.detail,
                        created_at=now,
                    )
                )
        session.flush()
        return conflict

    def get_by_id(self, session: Session, conflict_id: str) -> ConflictModel | None:
        return session.execute(
            select(ConflictModel).where(ConflictModel.id == conflict_id)
        ).scalar_one_or_none()

    def list_conflicts(
        self,
        session: Session,
        project_id: str | None = None,
        type: str | None = None,
        status: str | None = None,
        severity: str | None = None,
    ) -> list[ConflictModel]:
        stmt = select(ConflictModel)
        if project_id:
            stmt = stmt.where(ConflictModel.project_id == project_id)
        if type:
            stmt = stmt.where(ConflictModel.type == type)
        if status:
            stmt = stmt.where(ConflictModel.status == status)
        if severity:
            stmt = stmt.where(ConflictModel.severity == severity)
        return list(session.execute(stmt.order_by(ConflictModel.created_at.desc())).scalars().all())

    def resolve(
        self,
        session: Session,
        conflict_id: str,
        action: str,
        actor: str,
        note: str | None = None,
    ) -> ConflictModel | None:
        model = self.get_by_id(session, conflict_id)
        if not model:
            return None
        now = utc_now_iso()
        model.status = "resolved" if action != "dismiss" else "dismissed"
        model.resolution_action = action
        model.resolved_by = actor
        model.resolution_note = note
        model.resolved_at = now
        model.updated_at = now
        session.flush()
        return model
