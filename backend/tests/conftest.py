from collections.abc import Generator
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gpd.app import create_app
from gpd.db.engine import Database
from gpd.db.migrations import run_migrations
from gpd.settings import Settings


@pytest.fixture
def tmp_database_path(tmp_path: Path) -> Path:
    return tmp_path / "test_gpd.db"


@pytest.fixture
def settings(tmp_database_path: Path) -> Settings:
    return Settings(
        database_path=tmp_database_path,
        api_host="127.0.0.1",
        api_port=7337,
        app_version="0.1.0",
    )


@pytest.fixture
def database(tmp_database_path: Path) -> Generator[Database, None, None]:
    db = Database.open(tmp_database_path)
    run_migrations(db)
    yield db
    db.close()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def project_payload() -> dict[str, str]:
    return {
        "name": "checkout-service",
        "team_identifier": "team-payments",
        "repository_root": "/repos/checkout",
        "remote_url": "https://github.com/org/checkout.git",
        "default_branch": "main",
    }
