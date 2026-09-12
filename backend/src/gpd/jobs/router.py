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

@router.post(
    "/api/v1/jobs/{job_id}/retry",
    response_model=ApiEnvelope[JobResponse],
)
async def retry_job(
    job_id: str,
    database: Database = Depends(get_database),
) -> JSONResponse:
    def _txn():
        with database.session() as session:
            with session.begin():
                repo = JobRepository(session)
                job = repo.get_by_id(job_id)
                if job is None:
                    return ("missing", None, None)
                if job.state not in ("failed", "cancelled"):
                    return ("illegal", job.state, None)
                job.state = "queued"
                job.worker_id = None
                job.lease_expires_at = None
                job.error_message = None
                job.error_category = None
                job.progress = 0.0
                session.flush()
                return ("ok", None, _to_job_response(job).model_dump(mode="json"))
    status_, state, payload = await database.write(_txn)
    if status_ == "missing":
        raise ApiException(status_code=404, code="job_not_found", message=f"Job {job_id} not found")
    if status_ == "illegal":
        raise ApiException(status_code=409, code="job_not_retryable", message=f"Job {job_id} in state {state} cannot be retried")
    envelope = ApiEnvelope[JobResponse](ok=True, data=JobResponse.model_validate(payload))
    return JSONResponse(status_code=200, content=envelope.model_dump(mode="json"))


@router.post(
    "/api/v1/jobs/{job_id}/cancel",
    response_model=ApiEnvelope[JobResponse],
)
async def cancel_job(
    job_id: str,
    database: Database = Depends(get_database),
) -> JSONResponse:
    def _txn():
        with database.session() as session:
            with session.begin():
                repo = JobRepository(session)
                job = repo.get_by_id(job_id)
                if job is None:
                    return ("missing", None, None)
                if not repo.cancel(job_id):
                    return ("illegal", job.state, None)
                refreshed = repo.get_by_id(job_id)
                return ("ok", None, _to_job_response(refreshed).model_dump(mode="json"))
    status_, state, payload = await database.write(_txn)
    if status_ == "missing":
        raise ApiException(status_code=404, code="job_not_found", message=f"Job {job_id} not found")
    if status_ == "illegal":
        raise ApiException(status_code=409, code="job_not_cancellable", message=f"Job {job_id} in state {state} cannot be cancelled")
    envelope = ApiEnvelope[JobResponse](ok=True, data=JobResponse.model_validate(payload))
    return JSONResponse(status_code=200, content=envelope.model_dump(mode="json"))
