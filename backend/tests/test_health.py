from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from gpd.app import create_app
from gpd.settings import Settings


def test_health_reports_application_state(tmp_path):
    app = create_app(Settings(database_path=tmp_path / "gpd.db"))
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "0.1.0",
        "database": "pending",
    }


def test_health_reports_database_ok_when_running(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "0.1.0",
        "database": "ok",
    }


def test_health_reports_database_error_when_unavailable(app):
    with TestClient(app) as test_client:
        mock_db = MagicMock()
        mock_db.connect.side_effect = Exception("Database connection lost")
        app.state.database = mock_db

        response = test_client.get("/health")
        assert response.status_code == 503
        assert response.json() == {
            "status": "ok",
            "version": "0.1.0",
            "database": "error",
        }
