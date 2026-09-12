import json
import re
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from gpd.audit.service import append as append_audit_event
from gpd.db.models import IdempotencyKey, new_uuid, utc_now_iso
from gpd.llm.workflows.bug_extraction import BugExtraction
from gpd.tasks.models import (
    BugDetails,
    PublicIdCounter,
    Task,
    TaskFile,
    TaskKnowledge,
    TaskSource,
)
from gpd.tasks.schemas import TaskDetail, TaskSummary

FILE_PATH_REGEX = re.compile(r"\b(?:[a-zA-Z0-9_-]+/(?:[a-zA-Z0-9_.-]+/)*[a-zA-Z0-9_.-]+\.[a-zA-Z0-9_]+)\b")


def extract_file_paths(texts: list[str]) -> list[str]:
    seen: set[str] = set()
    paths: list[str] = []
    for text in texts:
        if not text:
            continue
        matches = FILE_PATH_REGEX.findall(text)
        for m in matches:
            if m not in seen:
                seen.add(m)
                paths.append(m)
    return paths


def task_to_detail(task: Task) -> TaskDetail:
    bug = task.bug_details
    repro = json.loads(bug.reproduction_steps) if bug and bug.reproduction_steps else None
    clues = json.loads(bug.technical_clues) if bug and bug.technical_clues else None
    parts = json.loads(bug.participants) if bug and bug.participants else []

    files = [f.file_path for f in task.task_files]
    sources = [s.source_id for s in task.task_sources]
    knowledge = [k.knowledge_id for k in task.task_knowledge]

    return TaskDetail(
        id=task.id,
        public_id=task.public_id,
        type=task.type,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        reporter=task.reporter,
        assignee=task.assignee,
        component=task.component,
        acceptance_criteria=task.acceptance_criteria,
        created_at=task.created_at,
        updated_at=task.updated_at,
        summary=bug.summary if bug else None,
        reproduction_steps=repro,
        actual_behavior=bug.actual_behavior if bug else None,
        expected_behavior=bug.expected_behavior if bug else None,
        environment=bug.environment if bug else None,
        severity=bug.severity if bug else None,
        affected_component=bug.affected_component if bug else None,
        technical_clues=clues,
        participants=parts,
        task_files=files,
        source_ids=sources,
        knowledge_ids=knowledge,
    )


class TaskRepository:
    def __init__(self, session_factory: Any):
        self.session_factory = session_factory

    def get(self, task_id: str, session: Session | None = None) -> Task | None:
        def _query(s: Session) -> Task | None:
            stmt = (
                select(Task)
                .where(Task.id == str(task_id))
                .options(
                    selectinload(Task.bug_details),
                    selectinload(Task.task_sources),
                    selectinload(Task.task_knowledge),
                    selectinload(Task.task_files),
                )
            )
            return s.scalars(stmt).first()

        if session is not None:
            return _query(session)
        with self.session_factory() as s:
            return _query(s)

    def get_by_ref(self, ref: str, session: Session | None = None) -> Task | None:
        def _query(s: Session) -> Task | None:
            stmt = (
                select(Task)
                .where((Task.id == str(ref)) | (Task.public_id == str(ref)))
                .options(
                    selectinload(Task.bug_details),
                    selectinload(Task.task_sources),
                    selectinload(Task.task_knowledge),
                    selectinload(Task.task_files),
                )
            )
            return s.scalars(stmt).first()

        if session is not None:
            return _query(session)
        with self.session_factory() as s:
            return _query(s)

    def list_tasks(
        self,
        status: str | None = None,
        priority: str | None = None,
        component: str | None = None,
        limit: int = 50,
        session: Session | None = None,
    ) -> list[Task]:
        def _query(s: Session) -> list[Task]:
            stmt = select(Task).order_by(Task.created_at.desc()).limit(limit)
            if status:
                stmt = stmt.where(Task.status == status)
            if priority:
                stmt = stmt.where(Task.priority == priority)
            if component:
                stmt = stmt.where(Task.component == component)
            return list(s.scalars(stmt).all())

        if session is not None:
            return _query(session)
        with self.session_factory() as s:
            return _query(s)

    def allocate_next_public_id(self, prefix: str, session: Session) -> str:
        counter = session.get(PublicIdCounter, prefix)
        if counter is None:
            counter = PublicIdCounter(prefix=prefix, last_value=1)
            session.add(counter)
        else:
            counter.last_value += 1
        session.flush()
        return f"{prefix}-{counter.last_value}"

    def create_bug_with_evidence(
        self,
        conversation: Any,
        extraction: BugExtraction,
        idempotency_key: str | None,
        session: Session,
    ) -> TaskDetail:
        now = utc_now_iso()
        conv_id = str(getattr(conversation, "id", ""))
        endpoint = f"/api/v1/conversations/{conv_id}/bugs"

        # Check idempotency
        if idempotency_key:
            stmt = select(IdempotencyKey).where(
                IdempotencyKey.endpoint == endpoint,
                IdempotencyKey.key == idempotency_key,
            )
            existing_key = session.scalars(stmt).first()
            if existing_key:
                stored = json.loads(existing_key.response_body)
                return TaskDetail.model_validate(stored)

        # Allocate BUG-N
        public_id = self.allocate_next_public_id("BUG", session)

        # Severity to priority
        sev = (extraction.severity.value or "").lower() if extraction.severity else ""
        priority_map = {"low": "low", "medium": "medium", "high": "high", "critical": "critical"}
        priority = priority_map.get(sev, "medium")

        # Component
        comp = (
            extraction.affected_component.value.strip()
            if extraction.affected_component and extraction.affected_component.value
            else None
        )

        # Acceptance criteria: NULL unless stated
        acceptance: str | None = None
        if extraction.acceptance_criteria and extraction.acceptance_criteria.value:
            val = extraction.acceptance_criteria.value.strip()
            if val:
                acceptance = val

        # Title & description
        title = extraction.title.value.strip() if extraction.title and extraction.title.value else "Untitled Bug"
        description = (
            extraction.description.value.strip()
            if extraction.description and extraction.description.value
            else ""
        )

        task = Task(
            id=new_uuid(),
            public_id=public_id,
            project_id=getattr(conversation, "project_id", None),
            type="bug",
            title=title,
            description=description,
            status="open",
            priority=priority,
            reporter=getattr(conversation, "reporter", None),
            component=comp,
            acceptance_criteria=acceptance,
            created_at=now,
            updated_at=now,
        )
        session.add(task)
        session.flush()

        # Bug details
        repro_steps = (
            extraction.reproduction_steps.value
            if extraction.reproduction_steps and extraction.reproduction_steps.value
            else None
        )
        tech_clues = (
            extraction.technical_clues.value
            if extraction.technical_clues and extraction.technical_clues.value
            else None
        )
        participants = extraction.participants or []

        bug = BugDetails(
            id=new_uuid(),
            task_id=task.id,
            summary=extraction.summary.value if extraction.summary else None,
            reproduction_steps=json.dumps(repro_steps) if repro_steps else None,
            actual_behavior=extraction.actual_behavior.value if extraction.actual_behavior else None,
            expected_behavior=extraction.expected_behavior.value if extraction.expected_behavior else None,
            environment=extraction.environment.value if extraction.environment else None,
            severity=extraction.severity.value if extraction.severity else None,
            affected_component=comp,
            technical_clues=json.dumps(tech_clues) if tech_clues else None,
            participants=json.dumps(participants) if participants else None,
            created_at=now,
        )
        session.add(bug)

        # Source link
        source_id = getattr(conversation, "source_id", None) or f"conversation:{conv_id}"
        ts = TaskSource(
            task_id=task.id,
            source_id=source_id,
            relationship_type="source",
            created_at=now,
        )
        session.add(ts)

        # Seed task_files from component and technical clues
        texts_to_scan = [comp or "", description]
        if tech_clues:
            texts_to_scan.extend(tech_clues)
        found_files = extract_file_paths(texts_to_scan)
        for fp in found_files:
            session.add(TaskFile(task_id=task.id, file_path=fp, created_at=now))

        # Audit event
        append_audit_event(
            session=session,
            actor="system",
            action="task.create_bug",
            target=task.id,
            metadata={"public_id": public_id, "conversation_id": conv_id},
        )

        session.flush()
        detail = task_to_detail(task)

        # Record idempotency key
        if idempotency_key:
            ik = IdempotencyKey(
                endpoint=endpoint,
                key=idempotency_key,
                request_hash="",
                response_status=200,
                response_body=json.dumps(detail.model_dump(mode="json")),
                created_at=now,
            )
            session.add(ik)
            session.flush()

        return detail
