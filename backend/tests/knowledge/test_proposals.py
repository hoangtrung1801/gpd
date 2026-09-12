from fastapi.testclient import TestClient
from gpd.knowledge.service import KnowledgeService


def test_confirm_proposal_creates_confirmed_knowledge_and_is_idempotent(client: TestClient, database):
    proj_res = client.post(
        "/api/v1/projects",
        json={"name": "prop-proj", "repository_root": "/tmp/prop-repo", "default_branch": "main"},
    )
    project_id = proj_res.json()["data"]["id"]

    sess_res = client.post(
        "/api/v1/sessions",
        json={"project_id": project_id, "task_id": "BUG-1", "developer": "alice"},
    )
    session_id = sess_res.json()["data"]["session"]["id"]

    finish_res = client.post(
        f"/api/v1/sessions/{session_id}/finish",
        json={"agent_summary": "Handled network timeout.", "diff": "diff --git a/a.py b/a.py\n"},
    )
    proposals = finish_res.json()["data"]["proposals"]
    assert len(proposals) >= 1
    proposal_id = proposals[0]["id"]

    # Confirm proposal
    confirm_res = client.post(
        f"/api/v1/knowledge/proposals/{proposal_id}/confirm",
        json={"actor": "alice", "note": "LGTM"},
    )
    assert confirm_res.status_code == 200
    confirmed_prop = confirm_res.json()["data"]
    assert confirmed_prop["status"] == "confirmed"
    assert confirmed_prop["reviewed_by"] == "alice"

    # Confirmed knowledge item exists
    k_svc = KnowledgeService(database)
    confirmed_items = k_svc.list_items(project_id, status="confirmed")
    assert len(confirmed_items) >= 1

    # Idempotent retry
    retry_res = client.post(
        f"/api/v1/knowledge/proposals/{proposal_id}/confirm",
        json={"actor": "alice", "note": "LGTM"},
    )
    assert retry_res.status_code == 200


def test_edit_proposal_creates_confirmed_knowledge_with_accepted_content(client: TestClient, database):
    proj_res = client.post(
        "/api/v1/projects",
        json={"name": "prop-proj-edit", "repository_root": "/tmp/prop-edit-repo", "default_branch": "main"},
    )
    project_id = proj_res.json()["data"]["id"]

    sess_res = client.post(
        "/api/v1/sessions",
        json={"project_id": project_id, "task_id": "BUG-1", "developer": "alice"},
    )
    session_id = sess_res.json()["data"]["session"]["id"]

    finish_res = client.post(
        f"/api/v1/sessions/{session_id}/finish",
        json={"agent_summary": "Updated retry logic.", "diff": "diff --git a/a.py b/a.py\n"},
    )
    proposal_id = finish_res.json()["data"]["proposals"][0]["id"]

    # Edit and confirm
    edit_res = client.post(
        f"/api/v1/knowledge/proposals/{proposal_id}/edit",
        json={
            "actor": "bob",
            "accepted_title": "Edited Retry Policy",
            "accepted_content": "Retry at most twice with exponential backoff",
            "note": "Refined policy",
        },
    )
    assert edit_res.status_code == 200
    data = edit_res.json()["data"]
    assert data["status"] == "edited_and_confirmed"
    assert data["accepted_title"] == "Edited Retry Policy"


def test_reject_proposal_does_not_create_knowledge(client: TestClient, database):
    proj_res = client.post(
        "/api/v1/projects",
        json={"name": "prop-proj-rej", "repository_root": "/tmp/prop-rej-repo", "default_branch": "main"},
    )
    project_id = proj_res.json()["data"]["id"]

    sess_res = client.post(
        "/api/v1/sessions",
        json={"project_id": project_id, "task_id": "BUG-1", "developer": "alice"},
    )
    session_id = sess_res.json()["data"]["session"]["id"]

    finish_res = client.post(
        f"/api/v1/sessions/{session_id}/finish",
        json={"agent_summary": "Temporary hack.", "diff": "diff --git a/a.py b/a.py\n"},
    )
    proposal_id = finish_res.json()["data"]["proposals"][0]["id"]

    reject_res = client.post(
        f"/api/v1/knowledge/proposals/{proposal_id}/reject",
        json={"actor": "bob", "reason": "Not reusable architectural knowledge"},
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["data"]["status"] == "rejected"

    k_svc = KnowledgeService(database)
    assert len(k_svc.list_items(project_id, status="confirmed")) == 0
