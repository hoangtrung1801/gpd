import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import importlib
from pathlib import Path
import uuid
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from gpd.api.errors import ApiEnvelope, ApiError, ApiException
from gpd.db.engine import Database
from gpd.db.migrations import run_migrations
from gpd.jobs.runner import JobRunner
from gpd.projects.service import ProjectService
from gpd.security.auth import BearerAuthMiddleware
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
        job_runner = JobRunner(database)

        app.state.database = database
        app.state.project_service = project_service
        app.state.job_runner = job_runner

        worker_id = f"worker-{uuid.uuid4().hex[:8]}"
        app.state.worker_id = worker_id
        stop_event = asyncio.Event()
        app.state.runner_stop = stop_event
        runner_task = asyncio.create_task(job_runner.run_forever(worker_id, stop_event))
        app.state.runner_task = runner_task

        yield

        stop_event.set()
        runner_task.cancel()
        try:
            await runner_task
        except (asyncio.CancelledError, Exception):
            pass

        database.close()
        app.state.database = None
        app.state.job_runner = None
        app.state.runner_task = None
    app = FastAPI(
        title="GPD API",
        version=resolved.app_version,
        lifespan=lifespan,
    )
    app.state.settings = resolved
    app.state.database = None
    app.state.project_service = None
    app.state.job_runner = None
    app.state.runner_task = None

    app.add_middleware(BearerAuthMiddleware)
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


    # SPA history fallback serving outside /api
    web_dist = resolved.web_dist_path
    if web_dist is None:
        potential_web_dirs = [
            Path("apps/web/dist"),
            Path(__file__).resolve().parents[3] / "apps" / "web" / "dist",
            Path("/app/web/dist"),
            Path("/app/static"),
        ]
        for p in potential_web_dirs:
            if p.exists() and (p / "index.html").is_file():
                web_dist = p
                break

    if web_dist and web_dist.exists():
        assets_dir = web_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str) -> Response:
            if (
                full_path.startswith("api/")
                or full_path == "api"
                or full_path.startswith("health")
                or full_path.startswith("docs")
                or full_path.startswith("openapi.json")
            ):
                raise HTTPException(status_code=404, detail="Not Found")
            file_path = web_dist / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            index_file = web_dist / "index.html"
            if index_file.is_file():
                return FileResponse(index_file)
            raise HTTPException(status_code=404, detail="Not Found")
    return app


app = create_app()
