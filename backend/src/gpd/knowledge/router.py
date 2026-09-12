from typing import Any
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from gpd.api.dependencies import get_database
from gpd.api.errors import ApiEnvelope
from gpd.db.engine import Database
from gpd.knowledge.embeddings import MockEmbeddingProvider
from gpd.knowledge.search import (
    HybridSearchService,
    SearchQuery,
    SqliteSearchIndex,
)

router = APIRouter(tags=["knowledge"])


class RankedChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    score: float
    lexical_score: float = 0.0
    vector_score: float = 0.0
    selection_reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    text: str = ""


class SearchResultResponse(BaseModel):
    hits: list[RankedChunkResponse] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def get_search_service(database: Database = Depends(get_database)) -> HybridSearchService:
    index = SqliteSearchIndex(database.session)
    provider = MockEmbeddingProvider()
    return HybridSearchService(search_index=index, embedding_provider=provider)


@router.get(
    "/api/v1/projects/{project_id}/search",
    response_model=ApiEnvelope[SearchResultResponse],
)
async def search_project(
    project_id: str,
    q: str = Query(..., min_length=1, description="Search query string"),
    limit: int = Query(10, ge=1, le=100, description="Max results"),
    task_id: str | None = Query(None, description="Optional linked task ID"),
    file: list[str] | None = Query(None, description="Optional related file paths"),
    component: str | None = Query(None, description="Optional affected component"),
    service: HybridSearchService = Depends(get_search_service),
) -> JSONResponse:
    query = SearchQuery(
        project_id=project_id,
        text=q,
        task_id=task_id,
        related_files=file or [],
        component=component,
        limit=limit,
    )
    result = service.search(query)
    hits = [
        RankedChunkResponse(
            chunk_id=h.chunk_id,
            score=h.score,
            lexical_score=h.lexical_score,
            vector_score=h.vector_score,
            selection_reasons=h.selection_reasons,
            metadata=h.metadata,
            text=h.text,
        )
        for h in result.hits
    ]
    response_data = SearchResultResponse(hits=hits, warnings=result.warnings)
    envelope = ApiEnvelope[SearchResultResponse](
        ok=True, data=response_data, warnings=result.warnings
    )
    return JSONResponse(status_code=200, content=envelope.model_dump(mode="json"))
