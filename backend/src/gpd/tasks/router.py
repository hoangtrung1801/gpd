from fastapi import APIRouter, Query, Request

from gpd.api.errors import ApiEnvelope, ApiException
from gpd.db.engine import Database
from gpd.tasks.schemas import TaskDetail, TaskSummary
from gpd.tasks.service import TaskService

router = APIRouter(tags=["tasks"])


@router.get("/api/v1/tasks", response_model=ApiEnvelope[list[TaskSummary]])
def list_tasks(
    request: Request,
    status: str | None = None,
    priority: str | None = None,
    component: str | None = None,
    limit: int = Query(50, ge=1, le=100),
) -> ApiEnvelope[list[TaskSummary]]:
    db: Database = request.app.state.database
    task_service = getattr(request.app.state, "task_service", None) or TaskService(db)
    tasks = task_service.list_tasks(
        status=status, priority=priority, component=component, limit=limit
    )
    return ApiEnvelope[list[TaskSummary]](ok=True, data=tasks)


@router.get("/api/v1/tasks/{task_ref}", response_model=ApiEnvelope[TaskDetail])
@router.get("/tasks/{task_ref}", response_model=ApiEnvelope[TaskDetail])
def get_task(task_ref: str, request: Request) -> ApiEnvelope[TaskDetail]:
    db: Database = request.app.state.database
    task_service = getattr(request.app.state, "task_service", None) or TaskService(db)
    detail = task_service.get_by_ref(task_ref)
    if detail is None:
        raise ApiException(
            status_code=404,
            code="task_not_found",
            message=f"Task {task_ref} not found",
        )
    return ApiEnvelope[TaskDetail](ok=True, data=detail)
