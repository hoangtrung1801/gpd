from fastapi.testclient import TestClient
from gpd.context.assembler import ContextAssembler, ContextRequest
from gpd.knowledge.service import KnowledgeService


def test_confirmed_proposal_is_retrieved_for_later_related_task(client: TestClient, database):
    # 1. Create project
    proj_res = client.post(
        "/api/v1/projects",
        json={"name": "reuse-proj", "repository_root": "/tmp/reuse-repo", "default_branch": "main"},
    )
    project_id = proj_res.json()["data"]["id"]

    # 2. Confirm knowledge item
    k_svc = KnowledgeService(database)
    item = k_svc.create_confirmed_item(
        project_id=project_id,
        type="implementation_constraint",
        title="Payment Error Handling",
        content="Always display user-friendly card error banner and avoid infinite spinners",
        evidence=[{"evidence_type": "decision", "target_id": "BUG-1"}],
    )

    # 3. Assemble context for a later related task
    assembler = ContextAssembler(database)
    package = assembler.assemble(
        ContextRequest(
            project_id=project_id,
            session_id="s-later",
            task_id="TASK-99",
            task_title="Checkout error screen",
            developer_prompt="implement error banner for payments",
            token_budget=1000,
        )
    )

    # 4. Assert confirmed knowledge is retrieved in package entries
    knowledge_entries = [e for e in package.entries if e.knowledge_id == item.id or "Payment Error Handling" in e.content]
    assert len(knowledge_entries) >= 1
    assert any(e.section == "requirements_decisions" for e in knowledge_entries)
