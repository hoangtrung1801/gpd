import pytest
from fastapi.testclient import TestClient
from gpd.conflicts.repository import ConflictRepository
from gpd.knowledge.service import KnowledgeService


def test_supersede_resolution_does_not_delete_old_claim(client: TestClient, database):
    # Setup project and knowledge items
    proj_res = client.post(
        "/api/v1/projects",
        json={"name": "res-proj-1", "repository_root": "/tmp/res-repo", "default_branch": "main"},
    )
    assert proj_res.status_code in (200, 201)
    project_id = proj_res.json()["data"]["id"]

    knowledge_svc = KnowledgeService(database)
    k1 = knowledge_svc.create_confirmed_item(
        project_id=project_id,
        type="decision",
        title="Retry policy v1",
        content="Retry payment three times",
        evidence=[{"evidence_type": "doc", "target_id": "prd:12"}],
    )
    k2 = knowledge_svc.create_confirmed_item(
        project_id=project_id,
        type="decision",
        title="Retry policy v2",
        content="Retries were reduced to one",
        evidence=[{"evidence_type": "slack", "target_id": "slack:m4"}],
    )

    # Trigger scan
    scan_res = client.post(f"/api/v1/conflicts/scan?project_id={project_id}")
    assert scan_res.status_code in (200, 201)
    conflicts = scan_res.json()["data"]
    assert len(conflicts) >= 1
    conflict_id = conflicts[0]["id"]

    # Resolve via supersede with winner k2
    res = client.post(
        f"/api/v1/conflicts/{conflict_id}/resolve",
        json={
            "action": "supersede",
            "actor": "alice",
            "note": "Updated per incident retrospective",
            "winner_id": k2.id,
        },
        headers={"Idempotency-Key": "resolve-1"},
    )
    assert res.status_code == 200
    resolved = res.json()["data"]
    assert resolved["status"] == "resolved"
    assert resolved["resolution_action"] == "supersede"

    # Old claim is NOT deleted; marked superseded
    k1_updated = knowledge_svc.get_item(k1.id)
    assert k1_updated is not None
    assert k1_updated.status == "superseded"
    assert len(k1_updated.evidence) >= 1

    # Winner stays confirmed
    k2_updated = knowledge_svc.get_item(k2.id)
    assert k2_updated is not None
    assert k2_updated.status == "confirmed"

    # Repeated scan suppresses already-resolved pair
    rescan = client.post(f"/api/v1/conflicts/scan?project_id={project_id}")
    assert rescan.status_code == 200
    # No new active conflict should be created for this pair
    new_conflicts = [c for c in rescan.json()["data"] if c["id"] != conflict_id and c["status"] == "active"]
    assert len(new_conflicts) == 0
