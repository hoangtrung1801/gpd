from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from gpd.api.dependencies import get_project_service, get_settings
from gpd.api.errors import ApiEnvelope, ApiError, ApiException
from gpd.projects.schemas import Project, ProjectCreate
from gpd.projects.service import ProjectService
from gpd.settings import Settings

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


class ProjectSettingsUpdate(BaseModel):
    name: str | None = None
    team_identifier: str | None = None
    default_branch: str | None = None
    llm_model: str | None = None
    embedding_model: str | None = None
    context_token_budget: int | None = None
    version: int = Field(description="Optimistic locking version")


class ProjectSettings(BaseModel):
    name: str
    team_identifier: str | None = None
    default_branch: str = "main"
    llm_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"
    context_token_budget: int = 8000
    retention_days: int = 30
    slack_credential_configured: bool = False
    llm_credential_configured: bool = False
    version: int = 1


@router.post("", response_model=ApiEnvelope[Project])
async def create_project(
    data: ProjectCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    service: ProjectService = Depends(get_project_service),
) -> JSONResponse:
    project = await service.register(data, idempotency_key=idempotency_key)
    status_code = 200 if getattr(project, "is_replay", False) else 201

    envelope = ApiEnvelope[Project](ok=True, data=project)
    return JSONResponse(status_code=status_code, content=envelope.model_dump(mode="json"))


@router.get("", response_model=ApiEnvelope[list[Project]])
async def list_projects(
    service: ProjectService = Depends(get_project_service),
) -> ApiEnvelope[list[Project]]:
    projects = await service.list_all()
    return ApiEnvelope[list[Project]](ok=True, data=projects)


@router.get("/{project_id}", response_model=ApiEnvelope[Project])
async def get_project(
    project_id: UUID,
    service: ProjectService = Depends(get_project_service),
) -> JSONResponse:
    project = await service.get_by_id(project_id)
    if project is None:
        envelope = ApiEnvelope[Project](
            ok=False,
            error=ApiError(code="not_found", message=f"Project '{project_id}' not found"),
        )
        return JSONResponse(status_code=404, content=envelope.model_dump(mode="json"))

    envelope = ApiEnvelope[Project](ok=True, data=project)
    return JSONResponse(status_code=200, content=envelope.model_dump(mode="json"))


_project_settings_state: dict[str, ProjectSettings] = {}


@router.get("/{project_id}/settings", response_model=ApiEnvelope[ProjectSettings])
async def get_project_settings(
    project_id: UUID,
    service: ProjectService = Depends(get_project_service),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    project = await service.get_by_id(project_id)
    if project is None:
        envelope = ApiEnvelope[ProjectSettings](
            ok=False,
            error=ApiError(code="not_found", message=f"Project '{project_id}' not found"),
        )
        return JSONResponse(status_code=404, content=envelope.model_dump(mode="json"))

    pid_str = str(project_id)
    if pid_str in _project_settings_state:
        data = _project_settings_state[pid_str]
    else:
        default_branch = project.repositories[0].default_branch if project.repositories else "main"
        slack_configured = bool(settings.slack_signing_secret and settings.slack_bot_token)
        llm_configured = True

        data = ProjectSettings(
            name=project.name,
            team_identifier=project.team_identifier,
            default_branch=default_branch,
            llm_model=settings.llm_model,
            embedding_model=settings.embedding_model,
            context_token_budget=settings.context_token_budget,
            retention_days=30,
            slack_credential_configured=slack_configured,
            llm_credential_configured=llm_configured,
            version=1,
        )
        _project_settings_state[pid_str] = data

    envelope = ApiEnvelope[ProjectSettings](ok=True, data=data)
    return JSONResponse(status_code=200, content=envelope.model_dump(mode="json"))


@router.patch("/{project_id}/settings", response_model=ApiEnvelope[ProjectSettings])
async def patch_project_settings(
    project_id: UUID,
    update: ProjectSettingsUpdate,
    service: ProjectService = Depends(get_project_service),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    project = await service.get_by_id(project_id)
    if project is None:
        envelope = ApiEnvelope[ProjectSettings](
            ok=False,
            error=ApiError(code="not_found", message=f"Project '{project_id}' not found"),
        )
        return JSONResponse(status_code=404, content=envelope.model_dump(mode="json"))

    pid_str = str(project_id)
    if pid_str not in _project_settings_state:
        default_branch = project.repositories[0].default_branch if project.repositories else "main"
        slack_configured = bool(settings.slack_signing_secret and settings.slack_bot_token)
        _project_settings_state[pid_str] = ProjectSettings(
            name=project.name,
            team_identifier=project.team_identifier,
            default_branch=default_branch,
            llm_model=settings.llm_model,
            embedding_model=settings.embedding_model,
            context_token_budget=settings.context_token_budget,
            retention_days=30,
            slack_credential_configured=slack_configured,
            llm_credential_configured=True,
            version=1,
        )

    current = _project_settings_state[pid_str]
    if update.version != current.version:
        envelope = ApiEnvelope[ProjectSettings](
            ok=False,
            error=ApiError(
                code="version_conflict",
                message=f"Settings version mismatch: expected {current.version}, got {update.version}",
            ),
        )
        return JSONResponse(status_code=409, content=envelope.model_dump(mode="json"))

    updated_data = ProjectSettings(
        name=update.name or current.name,
        team_identifier=update.team_identifier if update.team_identifier is not None else current.team_identifier,
        default_branch=update.default_branch or current.default_branch,
        llm_model=update.llm_model or current.llm_model,
        embedding_model=update.embedding_model or current.embedding_model,
        context_token_budget=update.context_token_budget or current.context_token_budget,
        retention_days=30,
        slack_credential_configured=current.slack_credential_configured,
        llm_credential_configured=True,
        version=current.version + 1,
    )
    _project_settings_state[pid_str] = updated_data
    envelope = ApiEnvelope[ProjectSettings](ok=True, data=updated_data)
    return JSONResponse(status_code=200, content=envelope.model_dump(mode="json"))
