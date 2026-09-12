from typing import Any, Literal
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from gpd.api.dependencies import get_database
from gpd.api.errors import ApiEnvelope, ApiException
from gpd.context.assembler import ContextAssembler, ContextRequest
from gpd.context.renderers import JsonContextRenderer, TextContextRenderer
from gpd.context.repository import ContextRepository
from gpd.context.schemas import ContextPackage
from gpd.db.engine import Database
from gpd.sessions.service import SessionService

router = APIRouter(prefix="/api/v1", tags=["context"])


def get_context_assembler(
    request: Request,
    database: Database = Depends(get_database),
) -> ContextAssembler:
    assembler: ContextAssembler | None = getattr(request.app.state, "context_assembler", None)
    if assembler is not None:
        return assembler
    assembler = ContextAssembler(database)
    request.app.state.context_assembler = assembler
    return assembler


def get_context_repository(
    request: Request,
) -> ContextRepository:
    repo: ContextRepository | None = getattr(request.app.state, "context_repository", None)
    if repo is not None:
        return repo
    repo = ContextRepository()
    request.app.state.context_repository = repo
    return repo


@router.get("/sessions/{session_id}/context")
async def get_session_context(
    session_id: str,
    format: Literal["json", "text"] = Query("json"),
    assembler: ContextAssembler = Depends(get_context_assembler),
    repository: ContextRepository = Depends(get_context_repository),
    database: Database = Depends(get_database),
) -> Any:
    # 1. Look for existing package for this session
    def _get_pkg():
        with database.session() as session:
            model = repository.get_latest_for_session(session, session_id)
            return model.to_schema() if model else None

    pkg = await database.write(_get_pkg)
    if pkg is None:
        # Assemble fresh package
        def _get_session_info():
            from gpd.sessions.repository import SessionRepository
            with database.session() as session:
                sess_repo = SessionRepository()
                s = sess_repo.get_by_id(session, session_id)
                return s.to_schema() if s else None

        sess = await database.write(_get_session_info)
        if sess is None:
            raise ApiException(
                status_code=404,
                code="session_not_found",
                message=f"Session with id '{session_id}' not found",
            )
        pkg = assembler.assemble(
            ContextRequest(
                project_id=sess.project_id,
                session_id=sess.id,
                task_id=sess.task_id,
                token_budget=1500,
            )
        )

    if format == "text":
        text_content = TextContextRenderer().render(pkg)
        return PlainTextResponse(text_content)

    json_payload = JsonContextRenderer().render(pkg)
    return JSONResponse(
        status_code=200,
        content=ApiEnvelope[dict[str, Any]](ok=True, data=json_payload).model_dump(mode="json"),
    )
