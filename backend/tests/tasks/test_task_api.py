import pytest

from gpd.conversations.schemas import ConversationCreate, ConversationMessageCreate
from gpd.conversations.service import ConversationService
from gpd.tasks.service import TaskService

pytestmark = pytest.mark.asyncio


def queue_valid_bug(fake_llm, title="Checkout hangs on expired card", sev="high", acceptance=None):
    fake_llm.respond(
        {
            "title": {"value": title, "confidence": 0.98, "evidence": ["m1"]},
            "summary": {"value": "Checkout error hang", "confidence": 0.95, "evidence": ["m1"]},
            "description": {"value": "Loading never ends after payment error.", "confidence": 0.95, "evidence": ["m1"]},
            "actual_behavior": {"value": "UI keeps loading forever.", "confidence": 0.99, "evidence": ["m1"]},
            "expected_behavior": {"value": "Show error banner.", "confidence": 0.94, "evidence": ["m1"]},
            "environment": {"value": None, "confidence": 0.0, "evidence": []},
            "severity": {"value": sev, "confidence": 0.9, "evidence": []},
            "affected_component": {"value": "payments", "confidence": 0.9, "evidence": []},
            "technical_clues": {"value": ["src/payment/checkout.ts", "docs/payment-adr.md"], "confidence": 0.85, "evidence": []},
            "participants": ["alice", "bob"],
            "acceptance_criteria": {"value": acceptance, "confidence": 0.9 if acceptance else 0.0, "evidence": []} if acceptance else None,
        }
    )


async def setup_conversation(test_app) -> str:
    conv_service: ConversationService = test_app.state.conversation_service
    conv = await conv_service.save_conversation(
        ConversationCreate(
            channel_id="C_CHECKOUT",
            thread_ts="1726137600.000100",
            title="Checkout discussion",
            messages=[
                ConversationMessageCreate(
                    external_message_id="m1",
                    author="alice",
                    text="Checkout hangs on expired card in src/payment/checkout.ts",
                    timestamp="1726137600.000100",
                    ordering=0,
                )
            ],
        )
    )
    return conv.id


async def test_create_bug_from_conversation(client, test_app, fake_llm):
    conv_id = await setup_conversation(test_app)
    queue_valid_bug(fake_llm, acceptance=None)

    response = client.post(f"/api/v1/conversations/{conv_id}/bugs")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["ok"] is True

    data = res_data["data"]
    assert data["public_id"] == "BUG-1"
    assert data["type"] == "bug"
    assert data["title"] == "Checkout hangs on expired card"
    assert data["priority"] == "high"  # mapped from severity="high"
    assert data["component"] == "payments"
    assert data["acceptance_criteria"] is None  # explicitly null unless stated
    assert data["summary"] == "Checkout error hang"
    assert "alice" in data["participants"]
    assert "src/payment/checkout.ts" in data["task_files"]


async def test_idempotency_key_replays_existing_task(client, test_app, fake_llm):
    conv_id = await setup_conversation(test_app)
    queue_valid_bug(fake_llm)

    headers = {"Idempotency-Key": "idemp-key-123"}
    resp1 = client.post(f"/api/v1/conversations/{conv_id}/bugs", headers=headers)
    assert resp1.status_code == 200
    bug1 = resp1.json()["data"]
    assert bug1["public_id"] == "BUG-1"

    # Second call with same idempotency key replays the same task without allocating BUG-2
    resp2 = client.post(f"/api/v1/conversations/{conv_id}/bugs", headers=headers)
    assert resp2.status_code == 200
    bug2 = resp2.json()["data"]
    assert bug2["public_id"] == "BUG-1"
    assert bug2["id"] == bug1["id"]


async def test_get_task_by_ref_resolves_uuid_and_public_id(client, test_app, fake_llm):
    conv_id = await setup_conversation(test_app)
    queue_valid_bug(fake_llm)

    create_resp = client.post(f"/api/v1/conversations/{conv_id}/bugs")
    assert create_resp.status_code == 200
    task_id = create_resp.json()["data"]["id"]
    public_id = create_resp.json()["data"]["public_id"]

    # Lookup by public ID via /api/v1/tasks/{ref}
    resp_pub = client.get(f"/api/v1/tasks/{public_id}")
    assert resp_pub.status_code == 200
    assert resp_pub.json()["data"]["id"] == task_id

    # Lookup by UUID via /api/v1/tasks/{ref}
    resp_uuid = client.get(f"/api/v1/tasks/{task_id}")
    assert resp_uuid.status_code == 200
    assert resp_uuid.json()["data"]["public_id"] == public_id

    # Lookup via /tasks/{ref} alias
    resp_alias = client.get(f"/tasks/{public_id}")
    assert resp_alias.status_code == 200
    assert resp_alias.json()["data"]["id"] == task_id


async def test_get_task_not_found_returns_404(client):
    response = client.get("/api/v1/tasks/NONEXISTENT-999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "task_not_found"


async def test_list_tasks_with_filters(client, test_app, fake_llm):
    conv_id = await setup_conversation(test_app)
    queue_valid_bug(fake_llm, title="Bug A", sev="critical")
    client.post(f"/api/v1/conversations/{conv_id}/bugs")

    queue_valid_bug(fake_llm, title="Bug B", sev="low")
    client.post(f"/api/v1/conversations/{conv_id}/bugs")

    # List all
    all_resp = client.get("/api/v1/tasks")
    assert all_resp.status_code == 200
    items = all_resp.json()["data"]
    assert len(items) >= 2

    # Filter by priority
    crit_resp = client.get("/api/v1/tasks?priority=critical")
    assert crit_resp.status_code == 200
    crit_items = crit_resp.json()["data"]
    assert all(t["priority"] == "critical" for t in crit_items)


async def test_acceptance_criteria_null_unless_stated(client, test_app, fake_llm):
    conv_id = await setup_conversation(test_app)

    # 1. Thread does not state acceptance criteria
    queue_valid_bug(fake_llm, acceptance=None)
    resp1 = client.post(f"/api/v1/conversations/{conv_id}/bugs")
    assert resp1.status_code == 200
    assert resp1.json()["data"]["acceptance_criteria"] is None

    # 2. Thread states acceptance criteria
    queue_valid_bug(fake_llm, acceptance="Show clear card expiration banner and re-enable submit button")
    resp2 = client.post(f"/api/v1/conversations/{conv_id}/bugs")
    assert resp2.status_code == 200
    assert resp2.json()["data"]["acceptance_criteria"] == "Show clear card expiration banner and re-enable submit button"
