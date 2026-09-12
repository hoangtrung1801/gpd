from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse

from gpd.api.dependencies import get_database
from gpd.api.errors import ApiEnvelope, ApiError, ApiException
from gpd.db.engine import Database
from gpd.sources.schemas import (
    SourceCreate,
    SourceDetailResponse,
    SourceIngestResult,
    SourceResponse,
)
from gpd.sources.service import SourceService

router = APIRouter(tags=["sources"])


def get_source_service(database: Database = Depends(get_database)) -> SourceService:
    return SourceService(database)


@router.post(
    "/api/v1/projects/{project_id}/sources",
    response_model=ApiEnvelope[SourceIngestResult],
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_source(
    project_id: str,
    data: SourceCreate,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    service: SourceService = Depends(get_source_service),
) -> JSONResponse:
    result = await service.ingest(
        project_id=project_id,
        data=data,
        idempotency_key=idempotency_key,
    )
    envelope = ApiEnvelope[SourceIngestResult](ok=True, data=result)
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content=envelope.model_dump(mode="json"),
    )


@router.get(
    "/api/v1/projects/{project_id}/sources",
    response_model=ApiEnvelope[list[SourceResponse]],
)
async def list_sources(
    project_id: str,
    limit: int = 50,
    cursor: str | None = None,
    service: SourceService = Depends(get_source_service),
) -> JSONResponse:
    sources = await service.list_by_project(project_id, limit=limit, cursor=cursor)
    envelope = ApiEnvelope[list[SourceResponse]](ok=True, data=sources)
    return JSONResponse(status_code=200, content=envelope.model_dump(mode="json"))


@router.get(
    "/api/v1/sources/{source_id}",
    response_model=ApiEnvelope[SourceDetailResponse],
)
async def get_source(
    source_id: str,
    service: SourceService = Depends(get_source_service),
) -> JSONResponse:
    detail = await service.get_by_id(source_id, with_details=True)
    if detail is None:
        raise ApiException(
            status_code=404,
            code="source_not_found",
            message=f"Source {source_id} not found",
        )
    envelope = ApiEnvelope[SourceDetailResponse](ok=True, data=detail)
    return JSONResponse(status_code=200, content=envelope.model_dump(mode="json"))


@router.get(
    "/api/v1/projects/{project_id}/sources/{source_id}",
    response_model=ApiEnvelope[SourceDetailResponse],
)
async def get_project_source(
    project_id: str,
    source_id: str,
    service: SourceService = Depends(get_source_service),
) -> JSONResponse:
    detail = await service.get_by_id(source_id, with_details=True)
    if detail is None or detail.project_id != project_id:
        raise ApiException(
            status_code=404,
            code="source_not_found",
            message=f"Source {source_id} not found in project {project_id}",
        )
    envelope = ApiEnvelope[SourceDetailResponse](ok=True, data=detail)
    return JSONResponse(status_code=200, content=envelope.model_dump(mode="json"))
