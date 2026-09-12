import json
from typing import Any
from sqlalchemy import select

from gpd.conversations.schemas import ConversationCreate, ConversationMessageCreate
from gpd.conversations.service import ConversationService
from gpd.db.engine import Database
from gpd.db.models import IdempotencyKey, utc_now_iso
from gpd.integrations.slack.client import FakeSlackClient, SlackClient, SlackMessage, SlackThread
from gpd.integrations.slack.parser import has_mention, is_bug_invocation, normalize_thread_messages
from gpd.llm.openai import OpenAILlmGateway
from gpd.llm.workflows.bug_extraction import BugExtractionWorkflow
from gpd.tasks.schemas import TaskDetail
from gpd.tasks.service import TaskService

class SlackService:
    def __init__(
        self,
        database: Database,
        task_service: TaskService | None = None,
        conversation_service: ConversationService | None = None,
        slack_client: SlackClient | None = None,
        llm_gateway: OpenAILlmGateway | None = None,
    ):
        self.database = database
        self.llm_gateway = llm_gateway or OpenAILlmGateway()
        workflow = BugExtractionWorkflow(self.llm_gateway)
        self.task_service = task_service or TaskService(database, bug_workflow=workflow)
        self.conversation_service = conversation_service or ConversationService(
            database, self.task_service
        )
        self.slack_client = slack_client or FakeSlackClient()

    async def handle_event(self, payload: dict[str, Any]) -> TaskDetail | None:
        event_id = payload.get("event_id")
        if not event_id:
            return None

        # Check event deduplication
        def _check_dedup() -> bool:
            with self.database.session() as session:
                stmt = select(IdempotencyKey).where(
                    IdempotencyKey.endpoint == "slack_event",
                    IdempotencyKey.key == str(event_id),
                )
                existing = session.scalars(stmt).first()
                if existing:
                    return True
                ik = IdempotencyKey(
                    endpoint="slack_event",
                    key=str(event_id),
                    request_hash="",
                    response_status=200,
                    response_body="",
                    created_at=utc_now_iso(),
                )
                session.add(ik)
                session.commit()
                return False

        is_duplicate = await self.database.write(_check_dedup)
        if is_duplicate:
            return None

        event = payload.get("event", {})
        channel = event.get("channel", "default_channel")
        thread_ts = event.get("thread_ts") or event.get("ts", "")
        text = event.get("text", "")

        # If not a mention, ignore
        if not has_mention(text):
            return None

        # Check if bug invocation
        if not is_bug_invocation(text):
            # General mention -> respond using OpenAI
            clean_text = text.replace("<@U0C1GAZ7JSY>", "").replace("@gpd", "").strip()
            prompt = clean_text or "Hello!"
            try:
                reply = await self.llm_gateway.generate_text(
                    prompt=prompt,
                    system="You are GPD, a helpful AI engineering assistant in Slack. Keep responses concise, helpful, and developer-friendly."
                )
            except Exception as e:
                reply = f"Hello! I am GPD. How can I assist you with your code or bugs today? (LLM note: {e})"
            await self.slack_client.post_message(channel, thread_ts, reply)
            return None

        # Fetch thread
        thread = await self.slack_client.fetch_thread(channel, thread_ts)
        if not thread.messages:
            # Fallback to payload's messages or single event message
            raw_msgs = payload.get("messages", [])
            if raw_msgs:
                thread = SlackThread(
                    channel_id=channel,
                    thread_ts=thread_ts,
                    messages=[
                        SlackMessage(
                            ts=m["ts"],
                            user=m.get("user", "U_UNKNOWN"),
                            text=m.get("text", ""),
                            thread_ts=m.get("thread_ts", thread_ts),
                        )
                        for m in raw_msgs
                    ],
                )
            else:
                thread = SlackThread(
                    channel_id=channel,
                    thread_ts=thread_ts,
                    messages=[
                        SlackMessage(
                            ts=event.get("ts", thread_ts),
                            user=event.get("user", "U_UNKNOWN"),
                            text=text,
                            thread_ts=thread_ts,
                        )
                    ],
                )

        normalized_msgs = normalize_thread_messages(thread)
        conv_create = ConversationCreate(
            channel_id=channel,
            thread_ts=thread_ts,
            title=f"Slack thread {channel}/{thread_ts}",
            messages=normalized_msgs,
        )

        conv = await self.conversation_service.save_conversation(conv_create)
        task_detail = await self.task_service.create_bug_from_conversation(
            conversation=conv, idempotency_key=f"slack:{event_id}"
        )

        # Post reply to Slack
        priority_label = (task_detail.priority or "medium").capitalize()
        area_label = task_detail.component or "General"
        reply_text = (
            f"Created {task_detail.public_id}\n\n"
            f"{task_detail.title}\n\n"
            f"Priority: {priority_label}\n"
            f"Area: {area_label}\n\n"
            f"I've linked this Slack discussion as source context."
        )
        await self.slack_client.post_message(channel, thread_ts, reply_text)

        return task_detail
