import math
import pytest

from gpd.knowledge.embeddings import validate_embedding, UnavailableEmbeddingProvider
from gpd.knowledge.search import HybridSearchService, SearchQuery


def test_fts_fallback_returns_warning_when_vectors_unavailable(search_without_vec: HybridSearchService):
    """Test that FTS5 search succeeds with warning when vector search is unavailable."""
    result = search_without_vec.search(SearchQuery(project_id="p1", text="payment invalid"))
    assert len(result.hits) > 0
    assert result.warnings == ["vector_search_unavailable"]


def test_direct_relationships_survive_without_any_search(search_without_any_index: HybridSearchService):
    """Test that direct relationships produce a minimal context package even if all indexes are down."""
    result = search_without_any_index.search(
        SearchQuery(project_id="p1", text="payment", task_id="task-1")
    )
    assert len(result.hits) > 0
    assert result.warnings == ["lexical_search_unavailable", "vector_search_unavailable"]
    assert result.hits[0].chunk_id == "directly-linked"


def test_embedding_dimension_validation():
    """Test that embeddings with wrong dimension are rejected."""
    with pytest.raises(ValueError, match="dimension mismatch"):
        validate_embedding([0.1] * 128, expected_dimension=384)


def test_non_finite_embedding_rejected():
    """Test that embeddings with NaN or Inf are rejected."""
    with pytest.raises(ValueError, match="non-finite"):
        validate_embedding([0.1, float("nan"), 0.3], expected_dimension=3)

    with pytest.raises(ValueError, match="non-finite"):
        validate_embedding([0.1, float("inf"), 0.3], expected_dimension=3)
