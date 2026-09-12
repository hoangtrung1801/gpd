from typing import Any
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from gpd.api.dependencies import get_database
from gpd.api.errors import ApiEnvelope, ApiException
from gpd.audit.service import append as append_audit
from gpd.db.engine import Database
from gpd.knowledge.proposals import (
    KnowledgeProposal,
    ProposalConfirmRequest,
    ProposalEditRequest,
    ProposalRejectRequest,
    ProposalRepository,
    utc_now_iso,
)
from gpd.knowledge.service import KnowledgeItemModel, KnowledgeService

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


def get_proposal_repo() -> ProposalRepository:
    return ProposalRepository()


@router.get("/proposals")
async def list_proposals(
    project_id: str | None = None,
    session_id: str | None = None,
    status: str | None = None,
    database: Database = Depends(get_database),
    repo: ProposalRepository = Depends(get_proposal_repo),
) -> ApiEnvelope[list[dict[str, Any]]]:
    def _query():
        with database.session() as session:
            proposals = repo.list_proposals(
                session, project_id=project_id, session_id=session_id, status=status
            )
            return [p.to_schema().model_dump(mode="json") for p in proposals]

    data = await database.write(_query)
    return ApiEnvelope[list[dict[str, Any]]](ok=True, data=data)


@router.get("/proposals/{proposal_id}")
async def get_proposal(
    proposal_id: str,
    database: Database = Depends(get_database),
    repo: ProposalRepository = Depends(get_proposal_repo),
) -> ApiEnvelope[dict[str, Any]]:
    def _query():
        with database.session() as session:
            p = repo.get_by_id(session, proposal_id)
            if not p:
                raise ApiException(
                    status_code=404,
                    code="proposal_not_found",
                    message=f"Proposal with id '{proposal_id}' not found",
                )
            return p.to_schema().model_dump(mode="json")

    data = await database.write(_query)
    return ApiEnvelope[dict[str, Any]](ok=True, data=data)


@router.post("/proposals/{proposal_id}/confirm")
async def confirm_proposal(
    proposal_id: str,
    data: ProposalConfirmRequest,
    database: Database = Depends(get_database),
    repo: ProposalRepository = Depends(get_proposal_repo),
) -> ApiEnvelope[dict[str, Any]]:
    def _txn():
        with database.session() as session:
            with session.begin():
                p = repo.get_by_id(session, proposal_id)
                if not p:
                    raise ApiException(
                        status_code=404,
                        code="proposal_not_found",
                        message=f"Proposal with id '{proposal_id}' not found",
                    )
                now = utc_now_iso()
                if p.status == "confirmed":
                    # Idempotent replay
                    return p.to_schema().model_dump(mode="json")

                p.status = "confirmed"
                p.reviewed_by = data.actor
                p.reviewed_at = now
                p.decision_note = data.note
                session.flush()

                # Promote to confirmed KnowledgeItem using the same transaction session
                k_svc = KnowledgeService(database)
                evidence_payload = [
                    {"evidence_type": e.evidence_type, "target_id": e.target_id, "detail": e.detail}
                    for e in p.evidence
                ]
                k_svc.create_confirmed_item(
                    project_id=p.project_id,
                    type=p.type,
                    title=p.title,
                    content=p.content,
                    confidence=p.confidence,
                    evidence=evidence_payload,
                    session=session,
                )

                append_audit(
                    session=session,
                    actor=data.actor,
                    action="proposal.confirm",
                    target=f"proposal:{p.id}",
                    metadata={"note": data.note},
                )

                return p.to_schema().model_dump(mode="json")

    res = await database.write(_txn)
    return ApiEnvelope[dict[str, Any]](ok=True, data=res)


@router.post("/proposals/{proposal_id}/edit")
async def edit_proposal(
    proposal_id: str,
    data: ProposalEditRequest,
    database: Database = Depends(get_database),
    repo: ProposalRepository = Depends(get_proposal_repo),
) -> ApiEnvelope[dict[str, Any]]:
    def _txn():
        with database.session() as session:
            with session.begin():
                p = repo.get_by_id(session, proposal_id)
                if not p:
                    raise ApiException(
                        status_code=404,
                        code="proposal_not_found",
                        message=f"Proposal with id '{proposal_id}' not found",
                    )
                now = utc_now_iso()
                p.status = "edited_and_confirmed"
                p.accepted_title = data.accepted_title
                p.accepted_content = data.accepted_content
                p.reviewed_by = data.actor
                p.reviewed_at = now
                p.decision_note = data.note
                session.flush()

                k_svc = KnowledgeService(database)
                evidence_payload = [
                    {"evidence_type": e.evidence_type, "target_id": e.target_id, "detail": e.detail}
                    for e in p.evidence
                ]
                k_svc.create_confirmed_item(
                    project_id=p.project_id,
                    type=p.type,
                    title=data.accepted_title,
                    content=data.accepted_content,
                    confidence=p.confidence,
                    evidence=evidence_payload,
                    session=session,
                )

                append_audit(
                    session=session,
                    actor=data.actor,
                    action="proposal.edit_confirm",
                    target=f"proposal:{p.id}",
                    metadata={"accepted_title": data.accepted_title, "note": data.note},
                )

                return p.to_schema().model_dump(mode="json")

    res = await database.write(_txn)
    return ApiEnvelope[dict[str, Any]](ok=True, data=res)


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str,
    data: ProposalRejectRequest,
    database: Database = Depends(get_database),
    repo: ProposalRepository = Depends(get_proposal_repo),
) -> ApiEnvelope[dict[str, Any]]:
    def _txn():
        with database.session() as session:
            with session.begin():
                p = repo.get_by_id(session, proposal_id)
                if not p:
                    raise ApiException(
                        status_code=404,
                        code="proposal_not_found",
                        message=f"Proposal with id '{proposal_id}' not found",
                    )
                now = utc_now_iso()
                p.status = "rejected"
                p.reviewed_by = data.actor
                p.reviewed_at = now
                p.decision_note = data.reason
                session.flush()

                append_audit(
                    session=session,
                    actor=data.actor,
                    action="proposal.reject",
                    target=f"proposal:{p.id}",
                    metadata={"reason": data.reason},
                )

                return p.to_schema().model_dump(mode="json")

    res = await database.write(_txn)
    return ApiEnvelope[dict[str, Any]](ok=True, data=res)
