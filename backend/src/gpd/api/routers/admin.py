from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from gpd.api.errors import ApiEnvelope, ApiError
from gpd.db.backup import BackupResult, BackupService

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class BackupRequest(BaseModel):
    destination: str | None = None


class BackupResponse(BaseModel):
    path: str
    sha256: str
    integrity_check: str
    size_bytes: int
    created_at: str


@router.post("/backup", response_model=ApiEnvelope[BackupResponse])
def create_backup(request: Request, body: BackupRequest | None = None) -> JSONResponse:
    database = getattr(request.app.state, "database", None)
    if database is None:
        envelope = ApiEnvelope[None](
            ok=False,
            error=ApiError(code="database_unavailable", message="Database not available"),
        )
        return JSONResponse(status_code=503, content=envelope.model_dump(mode="json"))

    backup_service = BackupService(database)
    dest_path = Path(body.destination) if body and body.destination else None
    result: BackupResult = backup_service.create(dest_path)

    envelope = ApiEnvelope[BackupResponse](
        ok=True,
        data=BackupResponse(
            path=result.path,
            sha256=result.sha256,
            integrity_check=result.integrity_check,
            size_bytes=result.size_bytes,
            created_at=result.created_at,
        ),
        warnings=[],
        error=None,
    )
    return JSONResponse(status_code=200, content=envelope.model_dump(mode="json"))
