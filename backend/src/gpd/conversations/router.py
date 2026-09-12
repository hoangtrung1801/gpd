from fastapi import APIRouter, Header, Request

from gpd.api.errors import ApiEnvelope
from gpd.conversations.service import ConversationService
from gpd.db.engine import Database
from gpd.tasks.schemas import TaskDetail
from gpd.tasks.service import TaskService

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.post("/{conversation_id}/bugs", response_model=ApiEnvelope[TaskDetail])
async def create_bug_from_conversation(
    conversation_id: str,
    request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> ApiEnvelope[TaskDetail]:
    db: Database = request.app.state.database
    task_service = getattr(request.app.state, "task_service", None) or TaskService(db)
    conv_service = getattr(request.app.state, "conversation_service", None) or ConversationService(
        db, task_service
    )

    detail = await conv_service.create_bug(conversation_id, idempotency_key=idempotency_key)
    return ApiEnvelope[TaskDetail](ok=True, data=detail)
