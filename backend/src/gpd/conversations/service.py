from typing import Any

from gpd.api.errors import ApiException
from gpd.conversations.repository import ConversationRepository
from gpd.conversations.schemas import ConversationCreate, ConversationRead
from gpd.db.engine import Database
from gpd.tasks.schemas import TaskDetail


class ConversationService:
    def __init__(self, database: Database, task_service: Any = None):
        self.database = database
        self.repository = ConversationRepository(database.session_factory)
        self.task_service = task_service

    def get(self, conversation_id: str) -> ConversationRead | None:
        with self.database.session() as s:
            conv = self.repository.get(conversation_id, session=s)
            if not conv:
                return None
            return ConversationRead.model_validate(conv)

    def require(self, conversation_id: str) -> ConversationRead:
        conv = self.get(conversation_id)
        if not conv:
            raise ApiException(
                status_code=404,
                code="conversation_not_found",
                message=f"Conversation {conversation_id} not found",
            )
        return conv

    async def save_conversation(self, data: ConversationCreate) -> ConversationRead:
        def _write() -> ConversationRead:
            with self.database.session() as s:
                with s.begin():
                    conv = self.repository.save_conversation(data, s)
                    s.flush()
                    return ConversationRead.model_validate(conv)

        return await self.database.write(_write)

    async def create_bug(
        self, conversation_id: str, idempotency_key: str | None = None
    ) -> TaskDetail:
        conv = self.require(conversation_id)
        if not self.task_service:
            from gpd.tasks.service import TaskService
            self.task_service = TaskService(self.database)

        return await self.task_service.create_bug_from_conversation(
            conversation=conv, idempotency_key=idempotency_key
        )
