from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Sequence

from gpd.api.errors import ApiException
from gpd.audit.service import append as append_audit
from gpd.conflicts.overlap import OverlapDetector, OverlapSessionInput, detect_work_overlaps
from gpd.conflicts.repository import ConflictRepository
from gpd.db.engine import Database
from gpd.sessions.git_inspector import GitInspector
from gpd.sessions.repository import SessionRepository
from gpd.sessions.schemas import (
    ChangedFile,
    CommitSummary,
    DeveloperSession,
    HeartbeatRequest,
    OverlapWarning,
    StartSessionRequest,
    StartSessionResponse,
)


class SessionService:
    def __init__(
        self,
        database: Database,
        session_repo: SessionRepository | None = None,
        conflict_repo: ConflictRepository | None = None,
        git_inspector: GitInspector | None = None,
        overlap_detector: OverlapDetector | None = None,
    ):
        self.database = database
        self.session_repo = session_repo or SessionRepository()
        self.conflict_repo = conflict_repo or ConflictRepository()
        self.git_inspector = git_inspector or GitInspector()
        self.overlap_detector = overlap_detector or OverlapDetector()

    def _compute_request_hash(self, data: StartSessionRequest) -> str:
        dump = data.model_dump(mode="json")
        canonical = json.dumps(dump, sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def start(
        self,
        data: StartSessionRequest,
        idempotency_key: str | None = None,
    ) -> tuple[DeveloperSession, list[OverlapWarning], bool]:
        endpoint = "POST /api/v1/sessions"
        request_hash = self._compute_request_hash(data)

        # 1. Run git inspector if repo_path provided (outside txn)
        changed_files = list(data.changed_files or [])
        commits: list[CommitSummary] = []
        branch = ""
        if data.repo_path:
            try:
                snapshot = self.git_inspector.inspect(Path(data.repo_path))
                branch = snapshot.branch
                if not changed_files:
                    changed_files = snapshot.changed_files
                commits = snapshot.recent_commits
            except Exception:
                # If git inspect fails, proceed with provided info
                pass

        def _txn() -> tuple[DeveloperSession, list[OverlapWarning], bool]:
            with self.database.session() as session:
                with session.begin():
                    # Idempotency check
                    if idempotency_key:
                        existing_key = self.session_repo.get_idempotency_key(
                            session, endpoint, idempotency_key
                        )
                        if existing_key is not None:
                            if existing_key.request_hash == request_hash:
                                payload = json.loads(existing_key.response_body)
                                sess = DeveloperSession.model_validate(payload["session"])
                                sess.is_replay = True
                                warnings = [
                                    OverlapWarning.model_validate(w) for w in payload.get("warnings", [])
                                ]
                                return sess, warnings, True
                            else:
                                raise ApiException(
                                    status_code=409,
                                    code="idempotency_conflict",
                                    message="Idempotency key mismatch with different payload",
                                )

                    # Check other active sessions in the project
                    self.session_repo.mark_stale_sessions(session, expiry_seconds=120)
                    active_models = self.session_repo.list_sessions(
                        session, project_id=data.project_id, status="active"
                    )

                    # Create session
                    model = self.session_repo.create(
                        session=session,
                        project_id=data.project_id,
                        task_id=data.task_id,
                        repository_id=data.repository_id,
                        developer=data.developer,
                        agent=data.agent,
                        branch=branch,
                        changed_files=changed_files,
                        commits=commits,
                    )

                    # Overlap detection
                    current_input = OverlapSessionInput(
                        session_id=model.id,
                        task_id=data.task_id,
                        files=[f.path for f in changed_files],
                        last_seen_at=model.last_seen_at,
                        status="active",
                    )
                    other_inputs = [
                        OverlapSessionInput(
                            session_id=m.id,
                            task_id=m.task_id,
                            files=[f.path for f in m.files],
                            last_seen_at=m.last_seen_at,
                            status=m.status,
                        )
                        for m in active_models
                        if m.id != model.id
                    ]

                    warnings = detect_work_overlaps(
                        current_input,
                        other_inputs,
                        detector=self.overlap_detector,
                        expiry_seconds=120,
                    )

                    # Persist conflict records for warnings
                    for w in warnings:
                        self.conflict_repo.create(
                            session=session,
                            project_id=data.project_id,
                            type="work_overlap",
                            severity=w.severity,
                            explanation=w.explanation,
                            detector_version="1.0",
                            evidence=w.evidence,
                        )

                    sess_schema = model.to_schema()

                    # Save idempotency key if provided
                    if idempotency_key:
                        resp_payload = {
                            "session": sess_schema.model_dump(mode="json"),
                            "warnings": [w.model_dump(mode="json") for w in warnings],
                        }
                        self.session_repo.save_idempotency_key(
                            session=session,
                            endpoint=endpoint,
                            key=idempotency_key,
                            request_hash=request_hash,
                            status_code=201,
                            response_body=json.dumps(resp_payload),
                        )

                    # Audit event
                    append_audit(
                        session=session,
                        actor=data.developer or data.agent or "developer",
                        action="session.start",
                        target=f"session:{model.id}",
                        metadata={"project_id": data.project_id, "task_id": data.task_id},
                    )

                    return sess_schema, warnings, False

        return await self.database.write(_txn)

    async def heartbeat(
        self,
        session_id: str,
        data: HeartbeatRequest,
    ) -> DeveloperSession:
        changed_files: list[ChangedFile] | None = data.changed_files
        if data.repo_path and changed_files is None:
            try:
                snapshot = self.git_inspector.inspect(Path(data.repo_path))
                changed_files = snapshot.changed_files
            except Exception:
                pass

        def _txn() -> DeveloperSession:
            with self.database.session() as session:
                with session.begin():
                    model = self.session_repo.update_heartbeat(
                        session=session,
                        session_id=session_id,
                        changed_files=changed_files,
                    )
                    if not model:
                        raise ApiException(
                            status_code=404,
                            code="session_not_found",
                            message=f"Session with id '{session_id}' not found",
                        )
                    return model.to_schema()

        return await self.database.write(_txn)

    async def get_by_id(self, session_id: str) -> DeveloperSession:
        def _txn() -> DeveloperSession:
            with self.database.session() as session:
                self.session_repo.mark_stale_sessions(session, expiry_seconds=120)
                model = self.session_repo.get_by_id(session, session_id)
                if not model:
                    raise ApiException(
                        status_code=404,
                        code="session_not_found",
                        message=f"Session with id '{session_id}' not found",
                    )
                return model.to_schema()

        return await self.database.write(_txn)

    async def list_sessions(
        self,
        project_id: str | None = None,
        task_id: str | None = None,
        status: str | None = None,
    ) -> list[DeveloperSession]:
        def _txn() -> list[DeveloperSession]:
            with self.database.session() as session:
                self.session_repo.mark_stale_sessions(session, expiry_seconds=120)
                models = self.session_repo.list_sessions(
                    session=session,
                    project_id=project_id,
                    task_id=task_id,
                    status=status,
                )
                return [m.to_schema() for m in models]

        return await self.database.write(_txn)
