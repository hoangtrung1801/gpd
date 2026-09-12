from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from gpd.sessions.completion import CompletionInput, sanitize_diff
from gpd.sessions.schemas import ChangedFile, CommitSummary


def test_sanitize_diff_redacts_secrets_and_bounds_length():
    raw_diff = (
        "diff --git a/config.py b/config.py\n"
        "--- a/config.py\n"
        "+++ b/config.py\n"
        "+SECRET_KEY = 'sk-live-1234567890abcdef1234567890'\n"
        "+API_TOKEN = 'secret_token_value'\n"
        "+def normal_code(): return True\n"
    )
    sanitized = sanitize_diff(raw_diff, max_length=200)
    assert "sk-live-" not in sanitized
    assert "REDACTED" in sanitized
    assert len(sanitized) <= 200


def test_finish_session_creates_proposals_not_confirmed_knowledge(client: TestClient, database):
    # Create project & session
    proj_res = client.post(
        "/api/v1/projects",
        json={"name": "finish-proj", "repository_root": "/tmp/finish-repo", "default_branch": "main"},
    )
    project_id = proj_res.json()["data"]["id"]

    sess_res = client.post(
        "/api/v1/sessions",
        json={"project_id": project_id, "task_id": "BUG-1", "developer": "alice"},
    )
    session_id = sess_res.json()["data"]["session"]["id"]

    # Finish session
    finish_res = client.post(
        f"/api/v1/sessions/{session_id}/finish",
        json={
            "agent_summary": "Normalized payment timeout handling to retry once.",
            "diff": "diff --git a/pay.py b/pay.py\n+timeout = 5\n",
        },
    )
    assert finish_res.status_code == 200
    data = finish_res.json()["data"]
    assert data["session"]["status"] in ("analyzing", "completed")
    assert len(data["proposals"]) >= 1
    # Check that proposals are pending
    for p in data["proposals"]:
        assert p["status"] == "pending"

    # Verify no confirmed knowledge was created yet (human gate)
    from gpd.knowledge.service import KnowledgeService
    k_svc = KnowledgeService(database)
    confirmed = k_svc.list_items(project_id, status="confirmed")
    assert len(confirmed) == 0
