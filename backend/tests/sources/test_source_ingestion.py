import asyncio
import pytest
from fastapi.testclient import TestClient

from gpd.db.engine import Database
from gpd.knowledge.indexer import KnowledgeIndexer
from gpd.sources.parsers import parse_markdown, validate_and_normalize_content, SourceValidationError


def test_duplicate_content_reuses_immutable_source(client: TestClient, project_id: str):
    """Test that identical content uploaded to a project reuses the immutable source record."""
    body = {"type": "prd", "title": "Checkout PRD", "content": "# Checkout\n\nCheckout flow spec."}
    first = client.post(f"/api/v1/projects/{project_id}/sources", json=body)
    second = client.post(f"/api/v1/projects/{project_id}/sources", json=body)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["ok"] is True
    assert second.json()["ok"] is True
    assert first.json()["data"]["source_id"] == second.json()["data"]["source_id"]
    assert second.json()["data"]["reused"] is True


def test_idempotency_key_replay_and_conflict(client: TestClient, project_id: str):
    """Test that Idempotency-Key returns cached response on replay and 409 on payload mismatch."""
    headers = {"Idempotency-Key": "source-upload-key-1"}
    body1 = {"type": "document", "title": "Doc 1", "content": "# Doc 1 content"}
    first = client.post(f"/api/v1/projects/{project_id}/sources", json=body1, headers=headers)
    assert first.status_code == 202

    # Replay identical payload
    second = client.post(f"/api/v1/projects/{project_id}/sources", json=body1, headers=headers)
    assert second.status_code == 202
    assert first.json()["data"]["source_id"] == second.json()["data"]["source_id"]

    # Replay with different payload under the same idempotency key
    body2 = {"type": "document", "title": "Doc 2 Modified", "content": "# Different content"}
    third = client.post(f"/api/v1/projects/{project_id}/sources", json=body2, headers=headers)
    assert third.status_code == 409
    assert third.json()["ok"] is False
    assert third.json()["error"]["code"] == "idempotency_conflict"


def test_nul_byte_rejected(client: TestClient, project_id: str):
    """Test that source content containing NUL bytes is rejected with 422."""
    body = {"type": "note", "title": "Nul note", "content": "hello\x00world"}
    res = client.post(f"/api/v1/projects/{project_id}/sources", json=body)
    assert res.status_code == 422
    assert res.json()["ok"] is False
    assert res.json()["error"]["code"] == "null_byte_detected"


def test_oversized_source_rejected(client: TestClient, project_id: str):
    """Test that source content exceeding 2 MiB is rejected with 413."""
    oversized = "a" * (2 * 1024 * 1024 + 10)
    body = {"type": "document", "title": "Giant", "content": oversized}
    res = client.post(f"/api/v1/projects/{project_id}/sources", json=body)
    assert res.status_code == 413
    assert res.json()["ok"] is False
    assert res.json()["error"]["code"] == "content_too_large"


def test_markdown_splitter_locators_and_token_estimates():
    """Test that parse_markdown splits on headings and calculates locators and token estimates."""
    md = """# Introduction
This is the intro section.

## Details
Here are the details with some more information.

### Sub-details
Even more granular pieces.
"""
    chunks = parse_markdown(md)
    assert len(chunks) == 3
    assert chunks[0].locator == "introduction"
    assert "intro section" in chunks[0].text
    assert chunks[0].token_estimate == max(1, len(chunks[0].text) // 4)

    assert chunks[1].locator == "details"
    assert "Here are the details" in chunks[1].text

    assert chunks[2].locator == "sub-details"
    assert "granular pieces" in chunks[2].text


def test_get_source_with_spans_and_chunks(client: TestClient, project_id: str, database: Database):
    """Test indexing a source and fetching details with spans and chunks."""
    body = {"type": "prd", "title": "Payment Spec", "content": "# Payment\n\nHandles card processing."}
    create_res = client.post(f"/api/v1/projects/{project_id}/sources", json=body)
    assert create_res.status_code == 202
    source_id = create_res.json()["data"]["source_id"]

    # Run indexer on the created source
    indexer = KnowledgeIndexer(database)
    state = asyncio.run(indexer.index_source(source_id))
    assert state == "ready"

    # Fetch source detail
    detail_res = client.get(f"/api/v1/sources/{source_id}")
    assert detail_res.status_code == 200
    data = detail_res.json()["data"]
    assert data["id"] == source_id
    assert data["state"] == "ready"
    assert len(data["spans"]) >= 1
    assert len(data["chunks"]) >= 1
    assert data["spans"][0]["locator"] == "payment"
    assert data["chunks"][0]["chunk_text"] == "# Payment\n\nHandles card processing."


def test_list_sources(client: TestClient, project_id: str):
    """Test listing sources for a project."""
    res = client.get(f"/api/v1/projects/{project_id}/sources")
    assert res.status_code == 200
    assert isinstance(res.json()["data"], list)
