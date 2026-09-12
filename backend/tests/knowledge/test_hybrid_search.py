import pytest
from fastapi.testclient import TestClient

from gpd.knowledge.search import HybridSearchService, SearchQuery
from gpd.knowledge.scoring import reciprocal_rank_fusion


def test_hybrid_search_rewards_direct_task_links(hybrid_search: HybridSearchService):
    """Test that chunks directly linked to the current task are rewarded with top rank and direct_task_link reason."""
    result = hybrid_search.search(
        SearchQuery(
            project_id="p1",
            text="expired payment method",
            task_id="task-1",
            related_files=["src/payment/service.ts"],
            limit=5,
        )
    )
    assert len(result.hits) > 0
    assert result.hits[0].chunk_id == "directly-linked"
    assert "direct_task_link" in result.hits[0].selection_reasons


def test_hybrid_search_boosts_exact_file_link(hybrid_search: HybridSearchService):
    """Test that chunks overlapping with related files receive the exact_file_link boost."""
    result = hybrid_search.search(
        SearchQuery(
            project_id="p1",
            text="payment processing",
            related_files=["src/payment/service.ts"],
            limit=5,
        )
    )
    assert len(result.hits) > 0
    file_boosted = [h for h in result.hits if "exact_file_link" in h.selection_reasons]
    assert len(file_boosted) >= 1


def test_hybrid_search_boosts_same_component(hybrid_search: HybridSearchService):
    """Test that chunks matching the query component receive the same_component boost."""
    result = hybrid_search.search(
        SearchQuery(
            project_id="p1",
            text="payment details",
            component="payment",
            limit=5,
        )
    )
    assert len(result.hits) > 0
    comp_boosted = [h for h in result.hits if "same_component" in h.selection_reasons]
    assert len(comp_boosted) >= 1


def test_reciprocal_rank_fusion_math():
    """Test reciprocal rank fusion formula: sum(1 / (k + rank))."""
    rankings = [
        ["c1", "c2", "c3"],
        ["c2", "c1", "c4"],
    ]
    scores = reciprocal_rank_fusion(rankings, k=60)
    expected_c1 = (1.0 / 61) + (1.0 / 62)
    assert pytest.approx(scores["c1"], 0.0001) == expected_c1
    assert pytest.approx(scores["c2"], 0.0001) == expected_c1
    assert pytest.approx(scores["c3"], 0.0001) == (1.0 / 63)


def test_search_api_route(client: TestClient, hybrid_search: HybridSearchService):
    """Test GET /api/v1/projects/{project_id}/search route returns 200 with hits."""
    res = client.get("/api/v1/projects/p1/search?q=payment&task_id=task-1&limit=5")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "hits" in body["data"]
    assert len(body["data"]["hits"]) > 0
    assert "score" in body["data"]["hits"][0]
