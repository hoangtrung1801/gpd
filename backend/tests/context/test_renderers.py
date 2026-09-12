from fastapi.testclient import TestClient
from gpd.context.renderers import JsonContextRenderer, TextContextRenderer
from gpd.context.schemas import ContextEntry, ContextPackage


def _sample_package() -> ContextPackage:
    entries = [
        ContextEntry(
            id="e1",
            section="task",
            content="Task: BUG-1 Fix checkout hang",
            rank=1,
            token_estimate=10,
        ),
        ContextEntry(
            id="e2",
            section="expected_actual",
            content="Actual: Hangs. Expected: Show error.",
            rank=2,
            token_estimate=10,
        ),
        ContextEntry(
            id="e3",
            section="discussion",
            content="Alice: The payment gateway timeout seems unhandled.",
            rank=3,
            token_estimate=15,
        ),
    ]
    return ContextPackage(
        id="pkg-1",
        session_id="s1",
        task_id="BUG-1",
        developer_query="checkout hang",
        token_budget=500,
        estimated_tokens=35,
        renderer_version="1.0",
        entries=entries,
        warnings=[],
    )


def test_text_and_json_renderers_share_entry_order():
    pkg = _sample_package()
    text = TextContextRenderer().render(pkg)
    payload = JsonContextRenderer().render(pkg)
    
    assert [entry["id"] for entry in payload["entries"]] == [e.id for e in pkg.entries]
    assert text.index("TASK") < text.index("ORIGINAL DISCUSSION")


def test_text_renderer_includes_warning_banners():
    pkg = _sample_package()
    pkg.warnings.append("vector_search_unavailable")
    text = TextContextRenderer().render(pkg)
    assert "WARNING: vector_search_unavailable" in text


def test_get_session_context_api_json_and_text(client: TestClient):
    # 1. Start a session
    proj_res = client.post(
        "/api/v1/projects",
        json={"name": "ctx-proj", "repository_root": "/tmp/ctx-repo", "default_branch": "main"},
    )
    assert proj_res.status_code in (200, 201)
    project_id = proj_res.json()["data"]["id"]

    sess_res = client.post(
        "/api/v1/sessions",
        json={"project_id": project_id, "task_id": "BUG-1", "developer": "alice"},
    )
    assert sess_res.status_code in (200, 201)
    session_id = sess_res.json()["data"]["session"]["id"]

    # 2. Get context in json
    json_res = client.get(f"/api/v1/sessions/{session_id}/context?format=json")
    assert json_res.status_code == 200
    data = json_res.json()["data"]
    assert "entries" in data
    assert len(data["entries"]) >= 1

    # 3. Get context in text
    text_res = client.get(f"/api/v1/sessions/{session_id}/context?format=text")
    assert text_res.status_code == 200
    assert "TASK" in text_res.text
