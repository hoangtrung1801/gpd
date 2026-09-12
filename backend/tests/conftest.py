from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import sys
from typing import Any, NamedTuple
import pytest
from fastapi.testclient import TestClient

# Ensure imports resolve across foundation and local worktree
foundation_src = Path("/home/work/gpd-worktrees/foundation/backend/src")
if foundation_src.exists() and str(foundation_src) not in sys.path:
    sys.path.insert(0, str(foundation_src))

local_src = Path(__file__).resolve().parent.parent / "src"
if str(local_src) not in sys.path:
    sys.path.insert(0, str(local_src))

import gpd
local_gpd = local_src / "gpd"
if local_gpd.exists() and str(local_gpd) not in gpd.__path__:
    gpd.__path__.append(str(local_gpd))

from gpd.app import create_app
from gpd.conversations.models import Conversation, ConversationMessage
from gpd.conversations.service import ConversationService
from gpd.db.engine import Database
from gpd.db.models import Base
from gpd.integrations.slack.client import FakeSlackClient
from gpd.integrations.slack.service import SlackService
from gpd.llm.recording import FakeLlmGateway
from gpd.llm.workflows.bug_extraction import BugExtractionWorkflow
from gpd.settings import Settings
from gpd.tasks.service import TaskService


@pytest.fixture
def fake_llm() -> FakeLlmGateway:
    return FakeLlmGateway()


@pytest.fixture
def bug_workflow(fake_llm: FakeLlmGateway) -> BugExtractionWorkflow:
    return BugExtractionWorkflow(fake_llm)


class MockMessage(NamedTuple):
    external_message_id: str
    author: str
    text: str
    timestamp: str
    ordering: int


class MockThread(NamedTuple):
    id: str
    channel_id: str
    thread_ts: str
    messages: list[MockMessage]


@pytest.fixture
def thread() -> MockThread:
    msgs = [
        MockMessage(external_message_id="m1", author="alice", text="Checkout hangs on expired card", timestamp="1.0", ordering=0),
        MockMessage(external_message_id="m2", author="bob", text="API returns payment_method_invalid", timestamp="2.0", ordering=1),
        MockMessage(external_message_id="m3", author="alice", text="UI keeps loading forever", timestamp="3.0", ordering=2),
        MockMessage(external_message_id="m4", author="carol", text="Expected error banner", timestamp="4.0", ordering=3),
    ]
    return MockThread(id="conv-123", channel_id="C_CHECKOUT", thread_ts="1.0", messages=msgs)


@pytest.fixture
def db(tmp_path: Path) -> Database:
    db_file = tmp_path / "test_gpd.db"
    database = Database.open(db_file)
    with database.connect() as conn:
        Base.metadata.create_all(conn)
        conn.commit()
    return database


@pytest.fixture
def test_app(db: Database, fake_llm: FakeLlmGateway) -> Any:
    settings = Settings(database_path=Path(db.engine.url.database or "test.db"))
    app = create_app(settings)

    # Wire services to app.state
    app.state.database = db
    workflow = BugExtractionWorkflow(fake_llm)
    task_service = TaskService(db, bug_workflow=workflow)
    conv_service = ConversationService(db, task_service=task_service)
    slack_client = FakeSlackClient()
    slack_service = SlackService(
        database=db,
        task_service=task_service,
        conversation_service=conv_service,
        slack_client=slack_client,
    )

    app.state.task_service = task_service
    app.state.conversation_service = conv_service
    app.state.slack_client = slack_client
    app.state.slack_service = slack_service
    app.state.settings = settings

    return app


@pytest.fixture
def client(test_app: Any) -> TestClient:
    return TestClient(test_app)


@pytest.fixture
def slack_client(client: TestClient) -> TestClient:
    return client


class SignedEvent(NamedTuple):
    body: bytes
    headers: dict[str, str]


@pytest.fixture
def signed_checkout_event(monkeypatch: Any) -> SignedEvent:
    secret = "test_signing_secret_123"
    monkeypatch.setenv("GPD_SLACK_SIGNING_SECRET", secret)

    payload = {
        "type": "event_callback",
        "event_id": "Ev_TEST_001",
        "event_time": 1726137604,
        "event": {
            "type": "app_mention",
            "user": "U_ALICE",
            "text": "<@U_GPD> create a bug task from this conversation",
            "ts": "1726137604.000500",
            "channel": "C_CHECKOUT",
            "thread_ts": "1726137600.000100",
        },
        "messages": [
            {
                "ts": "1726137600.000100",
                "user": "U_BOB",
                "text": "Checkout hangs on expired card in staging. Spinner never stops.",
            },
            {
                "ts": "1726137604.000500",
                "user": "U_ALICE",
                "text": "<@U_GPD> create a bug task from this conversation",
            },
        ],
    }
    body = json.dumps(payload).encode("utf-8")
    now_ts = str(int(datetime.now(timezone.utc).timestamp()))
    base = b"v0:" + now_ts.encode("utf-8") + b":" + body
    sig = "v0=" + hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Slack-Request-Timestamp": now_ts,
        "X-Slack-Signature": sig,
    }
    return SignedEvent(body=body, headers=headers)


@pytest.fixture
def old_signed_event(monkeypatch: Any) -> SignedEvent:
    secret = "test_signing_secret_123"
    monkeypatch.setenv("GPD_SLACK_SIGNING_SECRET", secret)

    payload = {"type": "event_callback", "event_id": "Ev_OLD_001"}
    body = json.dumps(payload).encode("utf-8")
    old_ts = str(int(datetime.now(timezone.utc).timestamp()) - 400)  # > 300s
    base = b"v0:" + old_ts.encode("utf-8") + b":" + body
    sig = "v0=" + hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Slack-Request-Timestamp": old_ts,
        "X-Slack-Signature": sig,
    }
    return SignedEvent(body=body, headers=headers)
