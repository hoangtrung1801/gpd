from fastapi.testclient import TestClient

from gpd.knowledge.service import KnowledgeService


def test_list_project_knowledge_returns_confirmed_items(client: TestClient, database):
    proj_res = client.post(
        "/api/v1/projects",
        json={"name": "know-proj", "repository_root": "/tmp/know-repo", "default_branch": "main"},
    )
    project_id = proj_res.json()["data"]["id"]
    KnowledgeService(database).create_confirmed_item(
        project_id=project_id,
        type="decision",
        title="Retry once",
        content="Retries were reduced to one.",
    )

    res = client.get(f"/api/v1/projects/{project_id}/knowledge")

    assert res.status_code == 200
    titles = [item["title"] for item in res.json()["data"]]
    assert "Retry once" in titles


def test_list_project_knowledge_unknown_project_is_404(client: TestClient):
    res = client.get("/api/v1/projects/does-not-exist/knowledge")

    assert res.status_code == 404
    assert res.json()["error"]["code"] == "project_not_found"
