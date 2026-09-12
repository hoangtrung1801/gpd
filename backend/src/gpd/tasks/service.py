import json
from typing import Any
from sqlalchemy import select

from gpd.db.engine import Database
from gpd.db.models import IdempotencyKey
from gpd.llm.recording import FakeLlmGateway
from gpd.llm.workflows.bug_extraction import BugExtractionWorkflow
from gpd.tasks.repository import TaskRepository, task_to_detail
from gpd.tasks.schemas import TaskDetail, TaskSummary


class TaskService:
    def __init__(
        self,
        database: Database,
        bug_workflow: BugExtractionWorkflow | None = None,
    ):
        self.database = database
        self.repository = TaskRepository(database.session_factory)
        self.bug_workflow = bug_workflow or BugExtractionWorkflow(FakeLlmGateway())

    async def create_bug_from_conversation(
        self,
        conversation: Any,
        idempotency_key: str | None = None,
    ) -> TaskDetail:
        conv_id = str(getattr(conversation, "id", ""))
        endpoint = f"/api/v1/conversations/{conv_id}/bugs"

        # Check idempotency cache first before calling LLM
        if idempotency_key:
            def _check_idemp() -> TaskDetail | None:
                with self.database.session() as session:
                    stmt = select(IdempotencyKey).where(
                        IdempotencyKey.endpoint == endpoint,
                        IdempotencyKey.key == idempotency_key,
                    )
                    existing_key = session.scalars(stmt).first()
                    if existing_key:
                        stored = json.loads(existing_key.response_body)
                        return TaskDetail.model_validate(stored)
                    return None

            cached = await self.database.write(_check_idemp)
            if cached is not None:
                return cached

        # LLM extraction runs OUTSIDE any DB transaction
        extraction = await self.bug_workflow.extract(conversation)

        def _write_txn() -> TaskDetail:
            with self.database.session() as session:
                with session.begin():
                    return self.repository.create_bug_with_evidence(
                        conversation=conversation,
                        extraction=extraction,
                        idempotency_key=idempotency_key,
                        session=session,
                    )

        return await self.database.write(_write_txn)

    def get_by_ref(self, ref: str) -> TaskDetail | None:
        task = self.repository.get_by_ref(ref)
        if task is None:
            return None
        return task_to_detail(task)

    def list_tasks(
        self,
        status: str | None = None,
        priority: str | None = None,
        component: str | None = None,
        limit: int = 50,
    ) -> list[TaskSummary]:
        tasks = self.repository.list_tasks(
            status=status, priority=priority, component=component, limit=limit
        )
        return [TaskSummary.model_validate(t) for t in tasks]
