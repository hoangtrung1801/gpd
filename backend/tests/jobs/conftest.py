from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from typing import Generator
import pytest

# Ensure backend/src from both worktrees are in sys.path
our_src = Path(__file__).resolve().parents[2] / "src"
if str(our_src) not in sys.path:
    sys.path.insert(0, str(our_src))

foundation_src = Path("/home/work/gpd-worktrees/foundation/backend/src")
if foundation_src.exists() and str(foundation_src) not in sys.path:
    sys.path.append(str(foundation_src))

try:
    import gpd
    our_gpd = our_src / "gpd"
    if our_gpd.exists() and str(our_gpd) not in gpd.__path__:
        gpd.__path__.append(str(our_gpd))
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.testclient import TestClient
from alembic.config import Config
from alembic import command
from sqlalchemy import text

from gpd.app import create_app
from gpd.db.engine import Database
from gpd.jobs.repository import JobRepository
from gpd.jobs.runner import JobRunner
from gpd.settings import Settings
import gpd.app
import gpd.db.migrations


class FakeClock:
    def __init__(self, start_time: datetime | None = None):
        self._current = start_time or datetime.now(timezone.utc)

    def now(self) -> datetime:
        return self._current

    def advance(self, seconds: float = 0, minutes: float = 0, hours: float = 0):
        self._current += timedelta(seconds=seconds, minutes=minutes, hours=hours)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def run_all_migrations(database: Database, *args, **kwargs) -> None:
    our_versions = str(Path(__file__).resolve().parents[2] / "migrations" / "versions")
    found_versions = "/home/work/gpd-worktrees/foundation/backend/migrations/versions"
    env_path = "/home/work/gpd-worktrees/foundation/backend/migrations"

    cfg = Config()
    cfg.set_main_option("script_location", env_path)
    cfg.set_main_option("version_locations", f"{found_versions} {our_versions}")

    with database.connect() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
        conn.commit()


gpd.app.run_migrations = run_all_migrations
gpd.db.migrations.run_migrations = run_all_migrations


@pytest.fixture
def database(tmp_path: Path) -> Generator[Database, None, None]:
    db_file = tmp_path / "test_jobs.db"
    db = Database.open(db_file)
    run_all_migrations(db)
    yield db
    db.close()


@pytest.fixture
def job_repository(database: Database, clock: FakeClock):
    session = database.session()
    repo = JobRepository(session, clock=clock)
    yield repo
    session.close()


@pytest.fixture
def runner(database: Database) -> JobRunner:
    return JobRunner(database, lease_seconds=30, poll_interval=0.05)


@pytest.fixture
def app(database: Database, tmp_path: Path) -> FastAPI:
    settings = Settings(
        database_path=tmp_path / "test_jobs.db",
        api_host="127.0.0.1",
        api_port=7337,
        app_version="0.1.0",
    )
    application = create_app(settings)
    application.state.database = database
    return application


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
