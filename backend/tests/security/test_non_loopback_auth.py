from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from gpd.app import create_app
from gpd.security.auth import verify_bearer_token
from gpd.settings import Settings, SettingsError


def test_non_loopback_binding_requires_access_token():
    with pytest.raises(SettingsError, match="access token"):
        Settings(api_host="0.0.0.0", access_token=None)


def test_non_loopback_binding_with_empty_token_fails():
    with pytest.raises(SettingsError, match="access token"):
        Settings(api_host="192.168.1.10", access_token="")


def test_loopback_binding_does_not_require_access_token():
    s1 = Settings(api_host="127.0.0.1", access_token=None)
    assert s1.api_host == "127.0.0.1"

    s2 = Settings(api_host="localhost", access_token=None)
    assert s2.api_host == "localhost"

    s3 = Settings(api_host="::1", access_token=None)
    assert s3.api_host == "::1"


def test_non_loopback_binding_with_token_succeeds():
    s = Settings(api_host="0.0.0.0", access_token="super-secret-token")
    assert s.access_token is not None
    assert s.access_token.get_secret_value() == "super-secret-token"


def test_protected_routes_require_bearer_token_when_configured(tmp_path: Path):
    settings = Settings(
        database_path=tmp_path / "gpd.db",
        api_host="127.0.0.1",
        access_token="test-access-token-123",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        # /api/v1/projects requires token
        res_no_auth = client.get("/api/v1/projects")
        assert res_no_auth.status_code == 401
        assert res_no_auth.json()["error"]["code"] == "unauthorized"

        # Invalid token rejected
        res_bad_auth = client.get(
            "/api/v1/projects",
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert res_bad_auth.status_code == 401

        # Valid token accepted
        res_good_auth = client.get(
            "/api/v1/projects",
            headers={"Authorization": "Bearer test-access-token-123"},
        )
        assert res_good_auth.status_code == 200

        # /health/ready requires token
        res_ready_no_auth = client.get("/health/ready")
        assert res_ready_no_auth.status_code == 401

        res_ready_good_auth = client.get(
            "/health/ready",
            headers={"Authorization": "Bearer test-access-token-123"},
        )
        assert res_ready_good_auth.status_code == 200

        # /health/live is minimal and OPEN
        res_live = client.get("/health/live")
        assert res_live.status_code == 200
        assert res_live.json() == {"status": "ok", "version": settings.app_version}


def test_loopback_without_token_allows_open_access(tmp_path: Path):
    settings = Settings(
        database_path=tmp_path / "gpd.db",
        api_host="127.0.0.1",
        access_token=None,
    )
    app = create_app(settings)

    with TestClient(app) as client:
        res_projects = client.get("/api/v1/projects")
        assert res_projects.status_code == 200

        res_ready = client.get("/health/ready")
        assert res_ready.status_code == 200

        res_live = client.get("/health/live")
        assert res_live.status_code == 200


def test_verify_bearer_token_constant_time():
    assert verify_bearer_token("Bearer mysecret", "mysecret") is True
    assert verify_bearer_token("bearer mysecret", "mysecret") is True
    assert verify_bearer_token("Bearer wrong", "mysecret") is False
    assert verify_bearer_token("Basic mysecret", "mysecret") is False
    assert verify_bearer_token("NotBearer", "mysecret") is False
    assert verify_bearer_token(None, "mysecret") is False
    assert verify_bearer_token("", "mysecret") is False
