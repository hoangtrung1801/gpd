from datetime import datetime, timezone
from typing import Any, Sequence
import uuid
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Float, ForeignKey, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

from gpd.db.models import Base


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_uuid() -> str:
    return str(uuid.uuid4())


class ProposalEvidenceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    proposal_id: str
    evidence_type: str
    target_id: str
    detail: str | None = None
    created_at: str


class KnowledgeProposal(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    session_id: str | None = None
    project_id: str
    type: str
    title: str
    content: str
    confidence: float
    status: str = "pending"  # pending, confirmed, edited_and_confirmed, rejected
    workflow_version: str = "1.0"
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    decision_note: str | None = None
    accepted_title: str | None = None
    accepted_content: str | None = None
    evidence: list[ProposalEvidenceSchema] = Field(default_factory=list)
    created_at: str


class ProposalConfirmRequest(BaseModel):
    actor: str = Field(min_length=1)
    note: str | None = None


class ProposalEditRequest(BaseModel):
    actor: str = Field(min_length=1)
    accepted_title: str = Field(min_length=1)
    accepted_content: str = Field(min_length=1)
    note: str | None = None


class ProposalRejectRequest(BaseModel):
    actor: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class KnowledgeProposalModel(Base):
    __tablename__ = "knowledge_proposals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(50), default="1.0", nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    accepted_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)

    evidence: Mapped[list["ProposalEvidenceModel"]] = relationship(
        "ProposalEvidenceModel", back_populates="proposal", cascade="all, delete-orphan"
    )

    def to_schema(self) -> KnowledgeProposal:
        return KnowledgeProposal(
            id=self.id,
            session_id=self.session_id,
            project_id=self.project_id,
            type=self.type,
            title=self.title,
            content=self.content,
            confidence=self.confidence,
            status=self.status,
            workflow_version=self.workflow_version,
            reviewed_by=self.reviewed_by,
            reviewed_at=self.reviewed_at,
            decision_note=self.decision_note,
            accepted_title=self.accepted_title,
            accepted_content=self.accepted_content,
            evidence=[e.to_schema() for e in self.evidence],
            created_at=self.created_at,
        )


class ProposalEvidenceModel(Base):
    __tablename__ = "proposal_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    proposal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_proposals.id", ondelete="CASCADE"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)

    proposal: Mapped["KnowledgeProposalModel"] = relationship(
        "KnowledgeProposalModel", back_populates="evidence"
    )

    def to_schema(self) -> ProposalEvidenceSchema:
        return ProposalEvidenceSchema(
            id=self.id,
            proposal_id=self.proposal_id,
            evidence_type=self.evidence_type,
            target_id=self.target_id,
            detail=self.detail,
            created_at=self.created_at,
        )


class ProposalRepository:
    def create(
        self,
        session: Session,
        project_id: str,
        type: str,
        title: str,
        content: str,
        confidence: float,
        session_id: str | None = None,
        evidence: Sequence[dict[str, Any]] | None = None,
        workflow_version: str = "1.0",
    ) -> KnowledgeProposalModel:
        now = utc_now_iso()
        model = KnowledgeProposalModel(
            id=new_uuid(),
            session_id=session_id,
            project_id=project_id,
            type=type,
            title=title,
            content=content,
            confidence=confidence,
            status="pending",
            workflow_version=workflow_version,
            created_at=now,
        )
        session.add(model)
        session.flush()

        if evidence:
            for ev in evidence:
                session.add(
                    ProposalEvidenceModel(
                        id=new_uuid(),
                        proposal_id=model.id,
                        evidence_type=ev.get("evidence_type", "reference"),
                        target_id=ev.get("target_id", ""),
                        detail=ev.get("detail"),
                        created_at=now,
                    )
                )
        session.flush()
        return model

    def get_by_id(self, session: Session, proposal_id: str) -> KnowledgeProposalModel | None:
        return session.execute(
            select(KnowledgeProposalModel).where(KnowledgeProposalModel.id == proposal_id)
        ).scalar_one_or_none()

    def list_proposals(
        self,
        session: Session,
        project_id: str | None = None,
        session_id: str | None = None,
        status: str | None = None,
    ) -> list[KnowledgeProposalModel]:
        stmt = select(KnowledgeProposalModel)
        if project_id:
            stmt = stmt.where(KnowledgeProposalModel.project_id == project_id)
        if session_id:
            stmt = stmt.where(KnowledgeProposalModel.session_id == session_id)
        if status:
            stmt = stmt.where(KnowledgeProposalModel.status == status)
        return list(session.execute(stmt.order_by(KnowledgeProposalModel.created_at.desc())).scalars().all())
