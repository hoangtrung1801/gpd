from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import pytest

pytestmark = pytest.mark.asyncio


def sign_payload(payload: dict, secret: str) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(payload).encode("utf-8")
    now_ts = str(int(datetime.now(timezone.utc).timestamp()))
    base = b"v0:" + now_ts.encode("utf-8") + b":" + body
    sig = "v0=" + hmac.new(secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Slack-Request-Timestamp": now_ts,
        "X-Slack-Signature": sig,
    }
    return body, headers


def queue_checkout_bug_extraction(fake_llm):
    fake_llm.respond(
        {
            "title": {"value": "Checkout hangs on expired card in staging", "confidence": 0.98, "evidence": ["1726137600.000100"]},
            "summary": {"value": "Checkout spinner never ends when expired card submitted", "confidence": 0.95, "evidence": ["1726137600.000100"]},
            "description": {"value": "POST /api/v1/checkout/pay returns payment_method_invalid (400) but UI state keeps loading=true.", "confidence": 0.96, "evidence": ["1726137601.000200"]},
            "actual_behavior": {"value": "UI state keeps loading=true and spinner never stops.", "confidence": 0.99, "evidence": ["1726137601.000200"]},
            "expected_behavior": {"value": "Show banner 'Card expired, please choose another payment method' and unfreeze button.", "confidence": 0.95, "evidence": ["1726137602.000300"]},
            "environment": {"value": "staging", "confidence": 0.9, "evidence": ["1726137603.000400"]},
            "severity": {"value": "high", "confidence": 0.9, "evidence": []},
            "affected_component": {"value": "payments", "confidence": 0.9, "evidence": ["1726137603.000400"]},
            "technical_clues": {"value": ["src/payment/checkout.ts"], "confidence": 0.9, "evidence": ["1726137603.000400"]},
            "participants": ["U_ALICE", "U_BOB", "U_CHARLIE"],
            "acceptance_criteria": None,
        }
    )


async def test_url_verification_synchronous_response(slack_client, monkeypatch):
    secret = "secret_abc"
    monkeypatch.setenv("GPD_SLACK_SIGNING_SECRET", secret)

    payload = {"type": "url_verification", "challenge": "challenge_token_12345"}
    body, headers = sign_payload(payload, secret)

    response = slack_client.post("/api/v1/integrations/slack/events", content=body, headers=headers)
    assert response.status_code == 200
    assert response.json()["challenge"] == "challenge_token_12345"


async def test_valid_slack_signature_is_accepted(slack_client, signed_checkout_event, fake_llm):
    queue_checkout_bug_extraction(fake_llm)

    response = slack_client.post(
        "/api/v1/integrations/slack/events",
        content=signed_checkout_event.body,
        headers=signed_checkout_event.headers,
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


async def test_invocation_filter_ignores_unsupported_text(slack_client, monkeypatch, test_app, fake_llm):
    secret = "secret_abc"
    monkeypatch.setenv("GPD_SLACK_SIGNING_SECRET", secret)

    payload = {
        "type": "event_callback",
        "event_id": "Ev_IGNORED_001",
        "event": {
            "type": "app_mention",
            "user": "U_ALICE",
            "text": "Hello world random discussion without bug keyword",
            "ts": "1726137600.000100",
            "channel": "C_GENERAL",
        },
    }
    body, headers = sign_payload(payload, secret)

    response = slack_client.post("/api/v1/integrations/slack/events", content=body, headers=headers)
    assert response.status_code == 200
    # No task created because invocation phrase was not matched
    assert response.json()["public_id"] is None
    assert len(fake_llm.requests) == 0


async def test_event_id_deduplication(slack_client, monkeypatch, test_app, fake_llm):
    secret = "secret_abc"
    monkeypatch.setenv("GPD_SLACK_SIGNING_SECRET", secret)

    payload = {
        "type": "event_callback",
        "event_id": "Ev_DEDUP_001",
        "event": {
            "type": "app_mention",
            "user": "U_ALICE",
            "text": "<@U_GPD> create a bug task from this conversation",
            "ts": "1726137604.000500",
            "channel": "C_CHECKOUT",
            "thread_ts": "1726137600.000100",
        },
        "messages": [
            {"ts": "1726137600.000100", "user": "U_BOB", "text": "Checkout hangs on expired card"},
            {"ts": "1726137604.000500", "user": "U_ALICE", "text": "<@U_GPD> create a bug task from this conversation"},
        ],
    }
    body, headers = sign_payload(payload, secret)

    queue_checkout_bug_extraction(fake_llm)
    resp1 = slack_client.post("/api/v1/integrations/slack/events", content=body, headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["public_id"] == "BUG-1"

    # Second delivery with same event_id is acknowledged with 200 but deduplicated (no second task or second LLM call)
    resp2 = slack_client.post("/api/v1/integrations/slack/events", content=body, headers=headers)
    assert resp2.status_code == 200
    assert len(fake_llm.requests) == 1


async def test_post_signed_checkout_fixture_workflow(slack_client, monkeypatch, test_app, fake_llm):
    secret = "checkout_secret"
    monkeypatch.setenv("GPD_SLACK_SIGNING_SECRET", secret)

    fixture_file = Path("fixtures/slack/checkout_bug_thread.json")
    fixture_data = json.loads(fixture_file.read_text(encoding="utf-8"))

    queue_checkout_bug_extraction(fake_llm)
    body, headers = sign_payload(fixture_data, secret)

    response = slack_client.post("/api/v1/integrations/slack/events", content=body, headers=headers)
    assert response.status_code == 200
    task = response.json()

    # Verify exact requirements from acceptance and plan line 1768-1771
    assert task["public_id"] == "BUG-1"
    assert task["acceptance_criteria"] is None
    assert task["summary"]
    assert task["participants"]
    assert "U_ALICE" in task["participants"]

    # Verify confirmation message was posted to Slack client
    slack_client_mock = test_app.state.slack_client
    assert len(slack_client_mock.posted_messages) >= 1
    last_msg = slack_client_mock.posted_messages[-1]
    assert "BUG-1" in last_msg["text"]
    assert "Checkout hangs on expired card in staging" in last_msg["text"]


async def test_slack_status_returns_booleans_only(slack_client, monkeypatch):
    monkeypatch.delenv("GPD_SLACK_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("GPD_SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)

    resp = slack_client.get("/api/v1/integrations/slack/status")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["installed"] is False
    assert data["signing_secret_configured"] is False
    assert data["bot_token_configured"] is False
    # Ensure no secret strings are leaked in JSON
    json_str = json.dumps(resp.json())
    assert "token" not in json_str or "bot_token_configured" in json_str
    assert "secret" not in json_str or "signing_secret_configured" in json_str

    # Test with secrets configured
    monkeypatch.setenv("GPD_SLACK_SIGNING_SECRET", "super_secret_signing_key")
    monkeypatch.setenv("GPD_SLACK_BOT_TOKEN", "xoxb-secret-token")

    resp2 = slack_client.get("/integrations/slack/status")
    assert resp2.status_code == 200
    data2 = resp2.json()["data"]
    assert data2["installed"] is True
    assert data2["signing_secret_configured"] is True
    assert data2["bot_token_configured"] is True
    # Verify no actual secret values are in response
    assert "super_secret_signing_key" not in resp2.text
    assert "xoxb-secret-token" not in resp2.text
