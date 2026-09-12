from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import importlib
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from gpd.api.errors import ApiEnvelope, ApiError, ApiException
from gpd.db.engine import Database
from gpd.db.migrations import run_migrations
from gpd.projects.service import ProjectService
from gpd.settings import Settings

ROUTER_MODULES = [
    "gpd.projects.router",
    "gpd.sources.router",
    "gpd.jobs.router",
    "gpd.tasks.router",
    "gpd.conversations.router",
    "gpd.sessions.router",
    "gpd.context.router",
    "gpd.conflicts.router",
    "gpd.slack.router",
    "gpd.integrations.slack.router",
    "gpd.api.routers.health",
    "gpd.api.routers.admin",
    "gpd.knowledge.router",
]


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database.open(resolved.database_path)
        run_migrations(database)
        project_service = ProjectService(database)

        app.state.database = database
        app.state.project_service = project_service

        yield

        database.close()
        app.state.database = None

    app = FastAPI(
        title="GPD API",
        version=resolved.app_version,
        lifespan=lifespan,
    )
    app.state.settings = resolved
    app.state.database = None
    app.state.project_service = None

    @app.exception_handler(ApiException)
    async def api_exception_handler(_request: Request, exc: ApiException) -> JSONResponse:
        envelope = ApiEnvelope[None](
            ok=False,
            warnings=exc.warnings,
            error=ApiError(
                code=exc.code,
                message=exc.message,
                retryable=exc.retryable,
                fields=exc.fields,
            ),
        )
        return JSONResponse(status_code=exc.status_code, content=envelope.model_dump(mode="json"))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors_map: dict[str, list[str]] = {}
        for err in exc.errors():
            loc = ".".join(str(part) for part in err.get("loc", []))
            msg = err.get("msg", "Invalid value")
            errors_map.setdefault(loc, []).append(msg)

        envelope = ApiEnvelope[None](
            ok=False,
            error=ApiError(
                code="validation_error",
                message="Request validation failed",
                retryable=False,
                fields=errors_map,
            ),
        )
        return JSONResponse(status_code=422, content=envelope.model_dump(mode="json"))

    @app.get("/health")
    def health() -> JSONResponse:
        db: Database | None = getattr(app.state, "database", None)
        if db is None:
            return JSONResponse(
                status_code=200,
                content={
                    "status": "ok",
                    "version": resolved.app_version,
                    "database": "pending",
                },
            )

        try:
            with db.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
            return JSONResponse(
                status_code=200,
                content={
                    "status": "ok",
                    "version": resolved.app_version,
                    "database": "ok",
                },
            )
        except Exception:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "ok",
                    "version": resolved.app_version,
                    "database": "error",
                },
            )

    # Auto-router registry
    for module_name in ROUTER_MODULES:
        try:
            mod = importlib.import_module(module_name)
            if hasattr(mod, "router"):
                app.include_router(mod.router)
            elif hasattr(mod, "register_router"):
                mod.register_router(app)
        except (ImportError, ModuleNotFoundError):
            continue

    return app


app = create_app()
