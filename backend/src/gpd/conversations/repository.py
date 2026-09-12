from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from gpd.conversations.models import Conversation, ConversationMessage
from gpd.conversations.schemas import ConversationCreate
from gpd.db.models import new_uuid, utc_now_iso


class ConversationRepository:
    def __init__(self, session_factory: Any):
        self.session_factory = session_factory

    def get(self, conversation_id: str, session: Session | None = None) -> Conversation | None:
        if session is not None:
            stmt = (
                select(Conversation)
                .where(Conversation.id == str(conversation_id))
                .options(selectinload(Conversation.messages))
            )
            return session.scalars(stmt).first()

        with self.session_factory() as s:
            stmt = (
                select(Conversation)
                .where(Conversation.id == str(conversation_id))
                .options(selectinload(Conversation.messages))
            )
            return s.scalars(stmt).first()

    def get_by_channel_and_thread(
        self, channel_id: str, thread_ts: str, session: Session | None = None
    ) -> Conversation | None:
        if session is not None:
            stmt = (
                select(Conversation)
                .where(
                    Conversation.channel_id == channel_id,
                    Conversation.thread_ts == thread_ts,
                )
                .options(selectinload(Conversation.messages))
            )
            return session.scalars(stmt).first()

        with self.session_factory() as s:
            stmt = (
                select(Conversation)
                .where(
                    Conversation.channel_id == channel_id,
                    Conversation.thread_ts == thread_ts,
                )
                .options(selectinload(Conversation.messages))
            )
            return s.scalars(stmt).first()

    def save_conversation(
        self, data: ConversationCreate, session: Session
    ) -> Conversation:
        existing = self.get_by_channel_and_thread(data.channel_id, data.thread_ts, session=session)
        now = utc_now_iso()
        if existing:
            if data.title is not None:
                existing.title = data.title
            if data.source_id is not None:
                existing.source_id = data.source_id
            if data.project_id is not None:
                existing.project_id = data.project_id
            existing.updated_at = now

            # Update/append messages
            existing_ext_ids = {m.external_message_id: m for m in existing.messages}
            for msg_in in data.messages:
                if msg_in.external_message_id in existing_ext_ids:
                    msg = existing_ext_ids[msg_in.external_message_id]
                    msg.text = msg_in.text
                    msg.author = msg_in.author
                    msg.timestamp = msg_in.timestamp
                    msg.ordering = msg_in.ordering
                else:
                    new_msg = ConversationMessage(
                        id=new_uuid(),
                        conversation_id=existing.id,
                        external_message_id=msg_in.external_message_id,
                        author=msg_in.author,
                        text=msg_in.text,
                        timestamp=msg_in.timestamp,
                        ordering=msg_in.ordering,
                        created_at=now,
                    )
                    session.add(new_msg)
            session.flush()
            return existing

        # Create new
        conv = Conversation(
            id=new_uuid(),
            project_id=data.project_id,
            source_id=data.source_id,
            channel_id=data.channel_id,
            thread_ts=data.thread_ts,
            title=data.title,
            created_at=now,
            updated_at=now,
        )
        session.add(conv)
        session.flush()

        for msg_in in data.messages:
            msg = ConversationMessage(
                id=new_uuid(),
                conversation_id=conv.id,
                external_message_id=msg_in.external_message_id,
                author=msg_in.author,
                text=msg_in.text,
                timestamp=msg_in.timestamp,
                ordering=msg_in.ordering,
                created_at=now,
            )
            session.add(msg)
        session.flush()
        return conv
