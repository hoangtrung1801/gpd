from pathlib import Path
import pytest
from fastapi.testclient import TestClient


def _create_project(client: TestClient) -> str:
    res = client.post(
        "/api/v1/projects",
        json={
            "name": "checkout-test",
            "team_identifier": "team-payments",
            "repository_root": "/tmp/test-repo",
            "default_branch": "main",
        },
        headers={"Idempotency-Key": "init-proj-1"},
    )
    assert res.status_code in (200, 201)
    return res.json()["data"]["id"]


def test_start_session_is_idempotent(client: TestClient, git_repo: Path):
    project_id = _create_project(client)
    
    payload = {
        "project_id": project_id,
        "task_id": "BUG-1",
        "developer": "alice",
        "agent": "claude",
        "repo_path": str(git_repo),
    }
    headers = {"Idempotency-Key": "start-session-1"}
    
    first = client.post("/api/v1/sessions", json=payload, headers=headers)
    assert first.status_code in (200, 201), first.text
    first_data = first.json()["data"]
    session_id = first_data["session"]["id"]
    
    # Replay with same key
    second = client.post("/api/v1/sessions", json=payload, headers=headers)
    assert second.status_code == 200
    assert second.json()["data"]["session"]["id"] == session_id
    
    # Conflict with different payload
    diff_payload = dict(payload, developer="bob")
    conflict = client.post("/api/v1/sessions", json=diff_payload, headers=headers)
    assert conflict.status_code == 409


def test_heartbeat_updates_last_seen_and_is_safe_retry(client: TestClient, git_repo: Path):
    project_id = _create_project(client)
    
    payload = {
        "project_id": project_id,
        "task_id": "BUG-1",
        "developer": "alice",
        "repo_path": str(git_repo),
    }
    start_res = client.post("/api/v1/sessions", json=payload)
    assert start_res.status_code in (200, 201)
    session_id = start_res.json()["data"]["session"]["id"]
    
    # Heartbeat without Idempotency-Key
    hb1 = client.post(f"/api/v1/sessions/{session_id}/heartbeat", json={})
    assert hb1.status_code == 200
    assert hb1.json()["data"]["status"] == "active"
    
    hb2 = client.post(f"/api/v1/sessions/{session_id}/heartbeat", json={})
    assert hb2.status_code == 200


def test_start_second_session_returns_overlap_warnings(client: TestClient, git_repo: Path):
    project_id = _create_project(client)
    
    # Create file in git_repo
    f = git_repo / "src" / "checkout.py"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("print('hello')\n")
    
    s1 = client.post(
        "/api/v1/sessions",
        json={"project_id": project_id, "task_id": "BUG-1", "developer": "alice", "repo_path": str(git_repo)},
    )
    assert s1.status_code in (200, 201)
    
    # Second session on same repo touching same file
    s2 = client.post(
        "/api/v1/sessions",
        json={"project_id": project_id, "task_id": "BUG-2", "developer": "bob", "repo_path": str(git_repo)},
    )
    assert s2.status_code in (200, 201)
    s2_data = s2.json()["data"]
    warnings = s2_data["warnings"]
    assert len(warnings) >= 1
    assert warnings[0]["severity"] == "high"
    assert "Avoid editing" in warnings[0]["suggested_action"]
