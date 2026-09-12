from fastapi import Request
from gpd.db.engine import Database
from gpd.projects.service import ProjectService
from gpd.settings import Settings


def get_settings(request: Request) -> Settings:
    return getattr(request.app.state, "settings", Settings())


def get_database(request: Request) -> Database:
    db = getattr(request.app.state, "database", None)
    if db is None:
        raise RuntimeError("Database not initialized on application state")
    return db


def get_project_service(request: Request) -> ProjectService:
    service = getattr(request.app.state, "project_service", None)
    if service is None:
        db = get_database(request)
        return ProjectService(db)
    return service
