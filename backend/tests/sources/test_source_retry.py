from fastapi.testclient import TestClient


def _ingest(client: TestClient, project_id: str) -> str:
    res = client.post(
        f"/api/v1/projects/{project_id}/sources",
        json={"type": "prd", "title": "Retry PRD", "content": "# retries"},
        headers={"Idempotency-Key": "retry-test-seed"},
    )
    assert res.status_code == 202
    return res.json()["data"]["source_id"]


def test_retry_source_requeues_ingestion(client: TestClient):
    proj_res = client.post(
        "/api/v1/projects",
        json={"name": "retry-proj", "repository_root": "/tmp/retry-repo", "default_branch": "main"},
    )
    project_id = proj_res.json()["data"]["id"]
    source_id = _ingest(client, project_id)

    res = client.post(f"/api/v1/sources/{source_id}/retry")

    assert res.status_code == 202
    assert res.json()["data"]["id"] == source_id
    assert res.json()["data"]["state"] == "queued"
    assert res.json()["data"]["job_id"]


def test_retry_unknown_source_is_404(client: TestClient):
    res = client.post("/api/v1/sources/does-not-exist/retry")

    assert res.status_code == 404
    assert res.json()["error"]["code"] == "source_not_found"
