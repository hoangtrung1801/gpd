import hashlib
import json
from typing import Any
from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse

from gpd.api.dependencies import get_database
from gpd.api.errors import ApiEnvelope, ApiException
from gpd.audit.service import append as append_audit
from gpd.conflicts.candidates import CandidateGenerator
from gpd.conflicts.contradictions import ContradictionDetector
from gpd.conflicts.repository import ConflictRepository
from gpd.conflicts.schemas import ConflictResponse, ResolveConflictRequest
from gpd.db.engine import Database
from gpd.knowledge.service import KnowledgeService
from gpd.knowledge.workflows.contradiction import Claim
from gpd.sessions.repository import SessionRepository
from gpd.sessions.schemas import ConflictEvidenceSchema

router = APIRouter(prefix="/api/v1/conflicts", tags=["conflicts"])


def get_conflict_repository() -> ConflictRepository:
    return ConflictRepository()


@router.post("/scan")
async def scan_conflicts(
    project_id: str = Query(...),
    database: Database = Depends(get_database),
    conflict_repo: ConflictRepository = Depends(get_conflict_repository),
) -> ApiEnvelope[list[dict[str, Any]]]:
    knowledge_svc = KnowledgeService(database)
    items = knowledge_svc.list_items(project_id, status=None)
    claims = [
        Claim(
            id=item.id,
            project_id=item.project_id,
            title=item.title,
            content=item.content,
            evidence_ids=[e.target_id for e in item.evidence] or [item.id],
            type=item.type,
        )
        for item in items
    ]

    def _txn():
        with database.session() as session:
            with session.begin():
                # Check existing conflicts to exclude previously scanned pairs
                existing_conflicts = conflict_repo.list_conflicts(session, project_id=project_id)
                excluded_pairs: set[tuple[str, str]] = set()
                for ec in existing_conflicts:
                    ev_ids = [e.target_id for e in ec.evidence if e.target_type == "knowledge"]
                    if len(ev_ids) >= 2:
                        excluded_pairs.add((ev_ids[0], ev_ids[1]))
                        excluded_pairs.add((ev_ids[1], ev_ids[0]))

                generator = CandidateGenerator()
                pairs = generator.generate_pairs(claims, excluded_pairs=excluded_pairs)
                detector = ContradictionDetector()

                for c1, c2 in pairs:
                    res = detector.detect(c1, c2)
                    # Only create conflict for ambiguous or contradictory results >= 0.70 confidence
                    if res.confidence >= 0.70 and res.classification in ("contradictory", "ambiguous"):
                        severity = "high" if res.classification == "contradictory" else "medium"
                        ev_list = [
                            ConflictEvidenceSchema(
                                kind="claim_pair",
                                target_type="knowledge",
                                target_id=c1.id,
                                detail=f"Claim '{c1.title}': {c1.content}",
                            ),
                            ConflictEvidenceSchema(
                                kind="claim_pair",
                                target_type="knowledge",
                                target_id=c2.id,
                                detail=f"Claim '{c2.title}': {c2.content}",
                            ),
                        ]
                        for eid in res.evidence_ids:
                            if eid not in (c1.id, c2.id):
                                ev_list.append(
                                    ConflictEvidenceSchema(
                                        kind="source_evidence",
                                        target_type="source",
                                        target_id=eid,
                                    )
                                )

                        conflict_repo.create(
                            session=session,
                            project_id=project_id,
                            type="contradictory_knowledge",
                            severity=severity,
                            explanation=res.explanation,
                            detector_version=detector.VERSION,
                            evidence=ev_list,
                        )

                # Return all conflicts for this project
                all_conflicts = conflict_repo.list_conflicts(session, project_id=project_id)
                result: list[dict[str, Any]] = []
                for c in all_conflicts:
                    result.append(
                        {
                            "id": c.id,
                            "project_id": c.project_id,
                            "type": c.type,
                            "severity": c.severity,
                            "status": c.status,
                            "explanation": c.explanation,
                            "detector_version": c.detector_version,
                            "resolution_action": c.resolution_action,
                            "resolved_by": c.resolved_by,
                            "resolution_note": c.resolution_note,
                            "resolved_at": c.resolved_at,
                            "created_at": c.created_at,
                            "updated_at": c.updated_at,
                            "evidence": [
                                {
                                    "id": e.id,
                                    "kind": e.kind,
                                    "target_type": e.target_type,
                                    "target_id": e.target_id,
                                    "score_component": e.score_component,
                                    "detail": e.detail,
                                }
                                for e in c.evidence
                            ],
                        }
                    )
                return result

    data = await database.write(_txn)
    return ApiEnvelope[list[dict[str, Any]]](ok=True, data=data)


@router.get("")
async def list_conflicts(
    project_id: str | None = None,
    type: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    database: Database = Depends(get_database),
    conflict_repo: ConflictRepository = Depends(get_conflict_repository),
) -> ApiEnvelope[list[dict[str, Any]]]:
    def _query():
        with database.session() as session:
            conflicts = conflict_repo.list_conflicts(
                session, project_id=project_id, type=type, status=status, severity=severity
            )
            return [
                {
                    "id": c.id,
                    "project_id": c.project_id,
                    "type": c.type,
                    "severity": c.severity,
                    "status": c.status,
                    "explanation": c.explanation,
                    "detector_version": c.detector_version,
                    "resolution_action": c.resolution_action,
                    "resolved_by": c.resolved_by,
                    "resolution_note": c.resolution_note,
                    "resolved_at": c.resolved_at,
                    "created_at": c.created_at,
                    "updated_at": c.updated_at,
                    "evidence": [
                        {
                            "id": e.id,
                            "kind": e.kind,
                            "target_type": e.target_type,
                            "target_id": e.target_id,
                            "score_component": e.score_component,
                            "detail": e.detail,
                        }
                        for e in c.evidence
                    ],
                }
                for c in conflicts
            ]

    data = await database.write(_query)
    return ApiEnvelope[list[dict[str, Any]]](ok=True, data=data)


@router.get("/{conflict_id}")
async def get_conflict(
    conflict_id: str,
    database: Database = Depends(get_database),
    conflict_repo: ConflictRepository = Depends(get_conflict_repository),
) -> ApiEnvelope[dict[str, Any]]:
    def _query():
        with database.session() as session:
            c = conflict_repo.get_by_id(session, conflict_id)
            if not c:
                raise ApiException(
                    status_code=404,
                    code="conflict_not_found",
                    message=f"Conflict with id '{conflict_id}' not found",
                )
            return {
                "id": c.id,
                "project_id": c.project_id,
                "type": c.type,
                "severity": c.severity,
                "status": c.status,
                "explanation": c.explanation,
                "detector_version": c.detector_version,
                "resolution_action": c.resolution_action,
                "resolved_by": c.resolved_by,
                "resolution_note": c.resolution_note,
                "resolved_at": c.resolved_at,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
                "evidence": [
                    {
                        "id": e.id,
                        "kind": e.kind,
                        "target_type": e.target_type,
                        "target_id": e.target_id,
                        "score_component": e.score_component,
                        "detail": e.detail,
                    }
                    for e in c.evidence
                ],
            }

    data = await database.write(_query)
    return ApiEnvelope[dict[str, Any]](ok=True, data=data)


@router.post("/{conflict_id}/resolve")
async def resolve_conflict(
    conflict_id: str,
    data: ResolveConflictRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    database: Database = Depends(get_database),
    conflict_repo: ConflictRepository = Depends(get_conflict_repository),
) -> JSONResponse:
    endpoint = f"POST /api/v1/conflicts/{conflict_id}/resolve"
    dump = data.model_dump(mode="json")
    request_hash = hashlib.sha256(json.dumps(dump, sort_keys=True).encode("utf-8")).hexdigest()

    def _txn():
        with database.session() as session:
            with session.begin():
                sess_repo = SessionRepository()
                # Idempotency check
                if idempotency_key:
                    existing_key = sess_repo.get_idempotency_key(session, endpoint, idempotency_key)
                    if existing_key is not None:
                        if existing_key.request_hash == request_hash:
                            payload = json.loads(existing_key.response_body)
                            return payload, 200
                        else:
                            raise ApiException(
                                status_code=409,
                                code="idempotency_conflict",
                                message="Idempotency key mismatch with different payload",
                            )

                c = conflict_repo.get_by_id(session, conflict_id)
                if not c:
                    raise ApiException(
                        status_code=404,
                        code="conflict_not_found",
                        message=f"Conflict with id '{conflict_id}' not found",
                    )

                # Execute resolution action
                if data.action == "supersede" and data.winner_id:
                    # Find loser id from knowledge evidence
                    ev_items = [e.target_id for e in c.evidence if e.target_type == "knowledge"]
                    for kid in ev_items:
                        if kid != data.winner_id:
                            # Mark loser superseded
                            from gpd.knowledge.service import KnowledgeItemModel
                            loser_model = session.query(KnowledgeItemModel).filter_by(id=kid).first()
                            if loser_model:
                                loser_model.status = "superseded"

                elif data.action in ("clarify_scope", "accept_conditional"):
                    from gpd.knowledge.service import KnowledgeItemModel, new_uuid, utc_now_iso
                    # Create clarified item linked to both
                    now = utc_now_iso()
                    title = data.clarified_title or f"Clarification on conflict {c.id[:8]}"
                    content = data.clarified_content or data.note
                    new_item = KnowledgeItemModel(
                        id=new_uuid(),
                        project_id=c.project_id,
                        type="decision",
                        title=title,
                        content=content,
                        confidence=1.0,
                        status="confirmed",
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(new_item)

                resolved = conflict_repo.resolve(
                    session=session,
                    conflict_id=conflict_id,
                    action=data.action,
                    actor=data.actor,
                    note=data.note,
                )

                # Audit event in same transaction
                append_audit(
                    session=session,
                    actor=data.actor,
                    action="conflict.resolve",
                    target=f"conflict:{c.id}",
                    metadata={"action": data.action, "note": data.note, "winner_id": data.winner_id},
                )

                result_dict = {
                    "id": resolved.id,
                    "project_id": resolved.project_id,
                    "type": resolved.type,
                    "severity": resolved.severity,
                    "status": resolved.status,
                    "explanation": resolved.explanation,
                    "detector_version": resolved.detector_version,
                    "resolution_action": resolved.resolution_action,
                    "resolved_by": resolved.resolved_by,
                    "resolution_note": resolved.resolution_note,
                    "resolved_at": resolved.resolved_at,
                    "created_at": resolved.created_at,
                    "updated_at": resolved.updated_at,
                }

                if idempotency_key:
                    sess_repo.save_idempotency_key(
                        session=session,
                        endpoint=endpoint,
                        key=idempotency_key,
                        request_hash=request_hash,
                        status_code=200,
                        response_body=json.dumps(result_dict),
                    )

                return result_dict, 200

    result, status_code = await database.write(_txn)
    envelope = ApiEnvelope[dict[str, Any]](ok=True, data=result)
    return JSONResponse(status_code=status_code, content=envelope.model_dump(mode="json"))
