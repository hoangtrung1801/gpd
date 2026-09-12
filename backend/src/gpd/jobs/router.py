import json
from typing import Any
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from gpd.api.dependencies import get_database
from gpd.api.errors import ApiEnvelope, ApiException
from gpd.db.engine import Database
from gpd.jobs.models import Job
from gpd.jobs.repository import JobRepository

router = APIRouter(tags=["jobs"])


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str | None = None
    type: str
    state: str
    idempotency_key: str | None = None
    payload: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    progress: float = 0.0
    attempts: int = 0
    max_attempts: int = 3
    worker_id: str | None = None
    error_category: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str
    completed_at: str | None = None


def _to_job_response(job: Job) -> JobResponse:
    payload = json.loads(job.payload_json) if job.payload_json else None
    result = json.loads(job.result_json) if job.result_json else None
    return JobResponse(
        id=job.id,
        project_id=job.project_id,
        type=job.type,
        state=job.state,
        idempotency_key=job.idempotency_key,
        payload=payload,
        result=result,
        progress=job.progress,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        worker_id=job.worker_id,
        error_category=job.error_category,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


@router.get(
    "/api/v1/jobs/{job_id}",
    response_model=ApiEnvelope[JobResponse],
)
async def get_job(
    job_id: str,
    database: Database = Depends(get_database),
) -> JSONResponse:
    def _fetch():
        with database.session() as session:
            repo = JobRepository(session)
            return repo.get_by_id(job_id)

    job = await database.write(_fetch)
    if job is None:
        raise ApiException(
            status_code=404,
            code="job_not_found",
            message=f"Job {job_id} not found",
        )

    envelope = ApiEnvelope[JobResponse](ok=True, data=_to_job_response(job))
    return JSONResponse(status_code=200, content=envelope.model_dump(mode="json"))


@router.get(
    "/api/v1/projects/{project_id}/jobs",
    response_model=ApiEnvelope[list[JobResponse]],
)
async def list_project_jobs(
    project_id: str,
    limit: int = 50,
    state: str | None = None,
    database: Database = Depends(get_database),
) -> JSONResponse:
    def _fetch():
        with database.session() as session:
            repo = JobRepository(session)
            return repo.list_by_project(project_id=project_id, limit=limit, state=state)

    jobs = await database.write(_fetch)
    data = [_to_job_response(j) for j in jobs]
    envelope = ApiEnvelope[list[JobResponse]](ok=True, data=data)
    return JSONResponse(status_code=200, content=envelope.model_dump(mode="json"))
