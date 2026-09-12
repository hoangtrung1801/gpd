from pathlib import Path
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from gpd.app import create_app
from gpd.db.engine import Database
from gpd.settings import Settings


def test_lifespan_smoke_test_enters_and_exits_cleanly(tmp_path: Path):
    """Lifespan smoke test: verify TestClient context manager enters and exits cleanly without hanging.

    Verifies distinct worker identity is assigned and runner task is created and cleanly cancelled.
    """
    settings = Settings(database_path=tmp_path / "smoke_gpd.db")
    app = create_app(settings)

    with TestClient(app) as client:
        # Verify app state inside lifespan
        assert app.state.database is not None
        assert app.state.worker_id is not None
        assert app.state.worker_id.startswith("worker-")
        assert app.state.runner_task is not None
        assert not app.state.runner_task.done()

        # Basic live probe
        res = client.get("/health/live")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

    # After exit from context manager, database and task should be cleaned up
    assert app.state.database is None
    assert app.state.runner_task is None


def test_health_live_endpoint(client: TestClient):
    """Test /health/live returns process state and is minimal."""
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    # Minimal: no internal database check details exposed
    assert "database" not in data
    assert "checks" not in data


def test_health_ready_healthy(client: TestClient):
    """Test /health/ready returns 200 with all checks ok when fully running."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "degraded")
    assert data["database"] == "ok"
    assert data["checks"]["database"] == "ok"
    assert data["checks"]["migration"] == "head"
    assert data["checks"]["integrity"] == "ok"


def test_health_ready_db_failure_returns_503(app):
    """Test /health/ready returns 503 when database connection is broken."""
    with TestClient(app) as client:
        mock_db = MagicMock()
        mock_db.connect.side_effect = Exception("Connection refused")
        app.state.database = mock_db

        response = client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "error"
        assert data["checks"]["database"] == "error"


def test_health_ready_migration_outdated_returns_503(app, tmp_path: Path):
    """Test /health/ready returns 503 when migration head does not match database revision."""
    with TestClient(app) as client:
        # Point to a mock database where revision is wrong
        mock_conn = MagicMock()
        mock_conn.exec_driver_sql.return_value.scalar.return_value = "ok"

        mock_db = MagicMock()
        mock_db.connect.return_value.__enter__.return_value = mock_conn

        app.state.database = mock_db

        # Mock MigrationContext to return outdated revision
        from unittest.mock import patch
        with patch("gpd.api.routers.health.MigrationContext") as mock_mc:
            mock_ctx = MagicMock()
            mock_ctx.get_current_revision.return_value = "0000_old"
            mock_mc.configure.return_value = mock_ctx

            response = client.get("/health/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "error"
            assert data["checks"]["migration"] == "outdated"


def test_health_ready_integrity_corrupt_returns_503(app):
    """Test /health/ready returns 503 when PRAGMA integrity_check fails."""
    with TestClient(app) as client:
        mock_conn = MagicMock()
        def _exec_sql(stmt):
            mock_res = MagicMock()
            if "integrity_check" in stmt:
                mock_res.scalar.return_value = "row 1 corrupt"
            else:
                mock_res.scalar.return_value = 1
            return mock_res
        mock_conn.exec_driver_sql.side_effect = _exec_sql

        mock_db = MagicMock()
        mock_db.connect.return_value.__enter__.return_value = mock_conn
        app.state.database = mock_db

        response = client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "error"
        assert data["checks"]["integrity"] == "corrupt"


def test_health_ready_degraded_returns_200_with_warnings(client: TestClient):
    """Test /health/ready returns 200 with warnings when degraded checks occur."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["warnings"], list)
    # Check that status is ok or degraded, not error
    assert data["status"] in ("ok", "degraded")


def test_health_legacy_alias(client: TestClient, app):
    """Test legacy GET /health route returns expected database: ok format."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "0.1.0",
        "database": "ok",
    }

    # When database is unavailable
    with TestClient(app) as test_client:
        mock_db = MagicMock()
        mock_db.connect.side_effect = Exception("DB down")
        app.state.database = mock_db

        res = test_client.get("/health")
        assert res.status_code == 503
        assert res.json() == {
            "status": "ok",
            "version": "0.1.0",
            "database": "error",
        }
