from fastapi.testclient import TestClient


def test_source_detail_includes_raw_content(client: TestClient):
    proj_res = client.post(
        "/api/v1/projects",
        json={"name": "content-proj", "repository_root": "/tmp/content-repo", "default_branch": "main"},
    )
    project_id = proj_res.json()["data"]["id"]
    src_res = client.post(
        f"/api/v1/projects/{project_id}/sources",
        json={"type": "note", "title": "Note", "content": "# readable content"},
        headers={"Idempotency-Key": "content-test-seed"},
    )
    source_id = src_res.json()["data"]["source_id"]

    res = client.get(f"/api/v1/sources/{source_id}")

    assert res.status_code == 200
    assert res.json()["data"]["content"] == "# readable content"
