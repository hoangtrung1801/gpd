from pathlib import Path
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from gpd.db.engine import Database

router = APIRouter(tags=["health"])


@router.get("/health/live")
def health_live(request: Request) -> JSONResponse:
    """Minimal liveness probe reporting only process state."""
    settings = getattr(request.app.state, "settings", None)
    version = getattr(settings, "app_version", "0.1.0")
    return JSONResponse(
        status_code=200,
        content={"status": "ok", "version": version},
    )


@router.get("/health/ready")
def health_ready(request: Request) -> JSONResponse:
    """Readiness probe checking database, migration head, integrity, FTS5, vectors, and worker."""
    settings = getattr(request.app.state, "settings", None)
    version = getattr(settings, "app_version", "0.1.0")
    db: Database | None = getattr(request.app.state, "database", None)

    if db is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "version": version,
                "database": "unavailable",
                "checks": {"database": "unavailable"},
                "warnings": [],
                "error": "Database not initialized",
            },
        )

    checks: dict[str, str] = {}
    warnings: list[str] = []
    critical_failure = False
    error_msg: str | None = None

    # 1. SELECT 1 database connectivity check (critical)
    try:
        with db.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = "error"
        critical_failure = True
        error_msg = f"Database connectivity error: {e}"

    # 2. Migration head check (critical)
    try:
        here = Path(__file__).resolve()
        potential = [
            here.parents[4] / "backend" / "alembic.ini",
            here.parents[3] / "alembic.ini",
            Path("backend/alembic.ini"),
            Path("alembic.ini"),
        ]
        cfg_path = None
        for p in potential:
            if p.exists():
                cfg_path = p
                break
        alembic_cfg = Config(str(cfg_path)) if cfg_path else Config("backend/alembic.ini")
        if cfg_path and cfg_path.exists():
            m_dir = cfg_path.parent / "migrations"
            if m_dir.exists():
                alembic_cfg.set_main_option("script_location", str(m_dir))

        script = ScriptDirectory.from_config(alembic_cfg)
        heads = script.get_heads()

        with db.connect() as conn:
            ctx = MigrationContext.configure(conn)
            current_rev = ctx.get_current_revision()

        if current_rev is not None and current_rev in heads:
            checks["migration"] = "head"
        else:
            checks["migration"] = "outdated"
            critical_failure = True
            if not error_msg:
                error_msg = f"Database migration revision ({current_rev}) not at head ({heads})"
    except Exception as e:
        checks["migration"] = "error"
        critical_failure = True
        if not error_msg:
            error_msg = f"Migration check failed: {e}"

    # 3. PRAGMA integrity_check (critical)
    try:
        with db.connect() as conn:
            res = conn.exec_driver_sql("PRAGMA integrity_check").scalar()
        if res == "ok":
            checks["integrity"] = "ok"
        else:
            checks["integrity"] = "corrupt"
            critical_failure = True
            if not error_msg:
                error_msg = f"Database integrity check failed: {res}"
    except Exception as e:
        checks["integrity"] = "error"
        critical_failure = True
        if not error_msg:
            error_msg = f"Database integrity check error: {e}"

    # 4. FTS5 probe (degraded -> warning)
    try:
        with db.connect() as conn:
            conn.exec_driver_sql("SELECT 1 FROM knowledge_chunks_fts LIMIT 1")
        checks["fts5"] = "ok"
    except Exception:
        checks["fts5"] = "degraded"
        warnings.append("fts5_search_unavailable")

    # 5. Vector health check (degraded -> warning)
    try:
        with db.connect() as conn:
            conn.exec_driver_sql("SELECT 1 FROM knowledge_chunks_vec LIMIT 1")
        checks["vector"] = "ok"
    except Exception:
        checks["vector"] = "degraded"
        warnings.append("vector_search_unavailable")
    runner_task = getattr(request.app.state, "runner_task", None)
    if runner_task is not None and not runner_task.done():
        checks["worker"] = "ok"
    else:
        checks["worker"] = "degraded"
        warnings.append("worker_lease_degraded")

    status_code = 503 if critical_failure else 200
    status_str = "error" if critical_failure else ("degraded" if warnings else "ok")

    return JSONResponse(
        status_code=status_code,
        content={
            "status": status_str,
            "version": version,
            "database": checks.get("database", "error"),
            "checks": checks,
            "warnings": warnings,
            "error": error_msg,
        },
    )


@router.get("/health")
def health_legacy(request: Request) -> JSONResponse:
    """Legacy health alias returning compact database state."""
    settings = getattr(request.app.state, "settings", None)
    version = getattr(settings, "app_version", "0.1.0")
    db: Database | None = getattr(request.app.state, "database", None)

    if db is None:
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "version": version,
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
                "version": version,
                "database": "ok",
            },
        )
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "status": "ok",
                "version": version,
                "database": "error",
            },
        )
