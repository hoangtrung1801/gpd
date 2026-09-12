from typing import Any
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse

from gpd.api.dependencies import get_database
from gpd.api.errors import ApiEnvelope, ApiException
from gpd.db.engine import Database
from gpd.sessions.schemas import (
    DeveloperSession,
    FinishSessionRequest,
    FinishSessionResponse,
    HeartbeatRequest,
    StartSessionRequest,
    StartSessionResponse,
)
from gpd.sessions.service import SessionService

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def get_session_service(
    request: Request,
    database: Database = Depends(get_database),
) -> SessionService:
    app_service: SessionService | None = getattr(request.app.state, "session_service", None)
    if app_service is not None:
        return app_service
    service = SessionService(database)
    request.app.state.session_service = service
    return service


@router.post("", response_model=ApiEnvelope[StartSessionResponse])
async def start_session(
    data: StartSessionRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    service: SessionService = Depends(get_session_service),
) -> JSONResponse:
    session, warnings, is_replay = await service.start(data, idempotency_key=idempotency_key)
    response_data = StartSessionResponse(session=session, warnings=warnings)
    envelope = ApiEnvelope[StartSessionResponse](ok=True, data=response_data)
    status_code = 200 if is_replay else 201
    return JSONResponse(status_code=status_code, content=envelope.model_dump(mode="json"))


@router.post("/{session_id}/heartbeat", response_model=ApiEnvelope[DeveloperSession])
async def heartbeat(
    session_id: str,
    data: HeartbeatRequest,
    service: SessionService = Depends(get_session_service),
) -> ApiEnvelope[DeveloperSession]:
    session = await service.heartbeat(session_id, data)
    return ApiEnvelope[DeveloperSession](ok=True, data=session)


@router.post("/{session_id}/finish", response_model=ApiEnvelope[FinishSessionResponse])
async def finish_session(
    session_id: str,
    data: FinishSessionRequest,
    service: SessionService = Depends(get_session_service),
) -> ApiEnvelope[FinishSessionResponse]:
    result = await service.finish(session_id, data)
    return ApiEnvelope[FinishSessionResponse](ok=True, data=result)


@router.get("", response_model=ApiEnvelope[list[DeveloperSession]])
async def list_sessions(
    project_id: str | None = None,
    task_id: str | None = None,
    status: str | None = None,
    service: SessionService = Depends(get_session_service),
) -> ApiEnvelope[list[DeveloperSession]]:
    sessions = await service.list_sessions(project_id=project_id, task_id=task_id, status=status)
    return ApiEnvelope[list[DeveloperSession]](ok=True, data=sessions)


@router.get("/{session_id}", response_model=ApiEnvelope[DeveloperSession])
async def get_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
) -> ApiEnvelope[DeveloperSession]:
    session = await service.get_by_id(session_id)
    return ApiEnvelope[DeveloperSession](ok=True, data=session)
