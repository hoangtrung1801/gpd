import uuid
from fastapi.testclient import TestClient


def test_register_project_success(client: TestClient, project_payload: dict):
    response = client.post("/api/v1/projects", json=project_payload)
    assert response.status_code == 201

    body = response.json()
    assert body["ok"] is True
    assert body["data"]["name"] == "checkout-service"
    assert body["data"]["team_identifier"] == "team-payments"
    assert len(body["data"]["repositories"]) == 1
    assert body["data"]["repositories"][0]["root_path"] == "/repos/checkout"
    assert body["data"]["repositories"][0]["default_branch"] == "main"
    assert body["error"] is None


def test_register_project_is_idempotent(client: TestClient, project_payload: dict):
    headers = {"Idempotency-Key": "init-checkout"}
    first = client.post("/api/v1/projects", json=project_payload, headers=headers)
    second = client.post("/api/v1/projects", json=project_payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert first.json()["data"]["name"] == second.json()["data"]["name"]


def test_register_project_idempotency_mismatch(client: TestClient, project_payload: dict):
    headers = {"Idempotency-Key": "init-checkout-mismatch"}
    first = client.post("/api/v1/projects", json=project_payload, headers=headers)
    assert first.status_code == 201

    mismatched_payload = dict(project_payload)
    mismatched_payload["name"] = "different-checkout"

    second = client.post("/api/v1/projects", json=mismatched_payload, headers=headers)
    assert second.status_code == 409
    assert second.json()["ok"] is False
    assert second.json()["error"]["code"] == "idempotency_conflict"


def test_register_duplicate_project_name(client: TestClient, project_payload: dict):
    first = client.post("/api/v1/projects", json=project_payload)
    assert first.status_code == 201

    different_repo = dict(project_payload)
    different_repo["repository_root"] = "/repos/different"

    second = client.post("/api/v1/projects", json=different_repo)
    assert second.status_code == 409
    assert second.json()["ok"] is False
    assert second.json()["error"]["code"] in ["project_already_exists", "conflict"]


def test_get_project_by_id(client: TestClient, project_payload: dict):
    create_res = client.post("/api/v1/projects", json=project_payload)
    assert create_res.status_code == 201
    project_id = create_res.json()["data"]["id"]

    get_res = client.get(f"/api/v1/projects/{project_id}")
    assert get_res.status_code == 200
    assert get_res.json()["ok"] is True
    assert get_res.json()["data"]["id"] == project_id
    assert get_res.json()["data"]["name"] == "checkout-service"

    fake_id = str(uuid.uuid4())
    not_found_res = client.get(f"/api/v1/projects/{fake_id}")
    assert not_found_res.status_code == 404
    assert not_found_res.json()["ok"] is False
    assert not_found_res.json()["error"]["code"] == "not_found"


def test_list_projects(client: TestClient, project_payload: dict):
    client.post("/api/v1/projects", json=project_payload)
    list_res = client.get("/api/v1/projects")
    assert list_res.status_code == 200
    assert list_res.json()["ok"] is True
    assert isinstance(list_res.json()["data"], list)
    assert len(list_res.json()["data"]) >= 1
    assert any(p["name"] == "checkout-service" for p in list_res.json()["data"])


def test_project_settings_lifecycle(client: TestClient, project_payload: dict):
    create_res = client.post("/api/v1/projects", json=project_payload)
    project_id = create_res.json()["data"]["id"]

    settings_res = client.get(f"/api/v1/projects/{project_id}/settings")
    assert settings_res.status_code == 200
    assert settings_res.json()["ok"] is True
    assert settings_res.json()["data"]["version"] == 1
    assert settings_res.json()["data"]["default_branch"] == "main"

    # Patch with valid version
    patch_res = client.patch(
        f"/api/v1/projects/{project_id}/settings",
        json={"default_branch": "release", "version": 1},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["ok"] is True
    assert patch_res.json()["data"]["version"] == 2
    assert patch_res.json()["data"]["default_branch"] == "release"

    # Patch with stale version -> 409
    stale_patch = client.patch(
        f"/api/v1/projects/{project_id}/settings",
        json={"default_branch": "develop", "version": 1},
    )
    assert stale_patch.status_code == 409
    assert stale_patch.json()["ok"] is False
    assert stale_patch.json()["error"]["code"] == "version_conflict"
