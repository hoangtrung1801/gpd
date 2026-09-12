import json
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field


class SlackMessage(BaseModel):
    ts: str
    user: str
    text: str
    thread_ts: str | None = None


class SlackThread(BaseModel):
    channel_id: str
    thread_ts: str
    messages: list[SlackMessage] = Field(default_factory=list)


class SlackClient:
    def __init__(self, bot_token: str | None = None):
        self.bot_token = bot_token

    async def fetch_thread(self, channel_id: str, thread_ts: str) -> SlackThread:
        # Default fixture fallback if no network token
        fixture_path = Path("fixtures/slack/checkout_bug_thread.json")
        if fixture_path.exists():
            data = json.loads(fixture_path.read_text(encoding="utf-8"))
            msgs = [
                SlackMessage(
                    ts=m["ts"],
                    user=m.get("user", "U_UNKNOWN"),
                    text=m.get("text", ""),
                    thread_ts=m.get("thread_ts", thread_ts),
                )
                for m in data.get("messages", [])
            ]
            return SlackThread(channel_id=channel_id, thread_ts=thread_ts, messages=msgs)
        return SlackThread(channel_id=channel_id, thread_ts=thread_ts, messages=[])

    async def post_message(
        self, channel_id: str, thread_ts: str, text: str
    ) -> dict[str, Any]:
        return {"ok": True, "channel": channel_id, "ts": thread_ts, "text": text}


class FakeSlackClient(SlackClient):
    def __init__(self) -> None:
        super().__init__()
        self.preloaded_threads: dict[tuple[str, str], SlackThread] = {}
        self.posted_messages: list[dict[str, Any]] = []

    def set_thread(self, channel_id: str, thread_ts: str, messages: list[dict[str, Any]]) -> None:
        parsed = [
            SlackMessage(
                ts=m["ts"],
                user=m.get("user", "U_UNKNOWN"),
                text=m.get("text", ""),
                thread_ts=m.get("thread_ts", thread_ts),
            )
            for m in messages
        ]
        self.preloaded_threads[(channel_id, thread_ts)] = SlackThread(
            channel_id=channel_id, thread_ts=thread_ts, messages=parsed
        )

    async def fetch_thread(self, channel_id: str, thread_ts: str) -> SlackThread:
        key = (channel_id, thread_ts)
        if key in self.preloaded_threads:
            return self.preloaded_threads[key]
        return await super().fetch_thread(channel_id, thread_ts)

    async def post_message(
        self, channel_id: str, thread_ts: str, text: str
    ) -> dict[str, Any]:
        msg = {"channel": channel_id, "thread_ts": thread_ts, "text": text}
        self.posted_messages.append(msg)
        return {"ok": True, **msg}
