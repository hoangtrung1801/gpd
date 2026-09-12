from collections.abc import Generator
from pathlib import Path
import subprocess
import sys
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure sys.path contains local and foundation source
here = Path(__file__).resolve().parent
local_src = here.parent / "src"
foundation_src = Path("/home/work/gpd-worktrees/foundation/backend/src")

for p in [str(local_src), str(foundation_src)]:
    if p not in sys.path and Path(p).exists():
        sys.path.insert(0, p)

# Enable namespace package extending
import gpd
import pkgutil
gpd.__path__ = pkgutil.extend_path(gpd.__path__, gpd.__name__)

# Mock run_migrations so that tests in isolated worktree don't require alembic.ini
import gpd.db.migrations
gpd.db.migrations.run_migrations = lambda *args, **kwargs: None

from gpd.app import create_app
from gpd.db.engine import Database
from gpd.db.models import Base
from gpd.settings import Settings


@pytest.fixture
def tmp_database_path(tmp_path: Path) -> Path:
    return tmp_path / "test_sessions_gpd.db"


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
    # Import all models so that Base.metadata has all tables
    import gpd.sessions.repository
    import gpd.conflicts.repository
    try:
        import gpd.context.repository
        import gpd.knowledge.service
    except (ImportError, ModuleNotFoundError):
        pass
    with db.connect() as conn:
        Base.metadata.create_all(bind=conn)
        conn.commit()
    yield db
    db.close()


@pytest.fixture
def app(settings: Settings, database: Database) -> FastAPI:
    application = create_app(settings)
    application.state.database = database
    return application


@pytest.fixture
def client(app: FastAPI, database: Database) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        # Also ensure app.state.database is set
        app.state.database = database
        yield test_client


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "test_repo"
    repo.mkdir()
    env = {
        "GIT_AUTHOR_NAME": "Tester",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Tester",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "PATH": "/usr/bin:/bin",
    }
    subprocess.run(["git", "init", "-b", "feature/payment"], cwd=repo, check=True, capture_output=True, env=env)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, env=env)
    
    # Create initial commit
    (repo / "README.md").write_text("# Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, env=env)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, check=True, env=env)
    return repo
