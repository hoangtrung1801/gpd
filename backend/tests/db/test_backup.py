import hashlib
from pathlib import Path
import sqlite3
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from gpd.db.backup import BackupResult, BackupService
from gpd.db.engine import Database


@pytest.fixture
def backup_service(database: Database, tmp_path: Path) -> BackupService:
    return BackupService(database, backup_dir=tmp_path / "backups")


def test_online_backup_is_integrity_checked(database: Database, backup_service: BackupService, tmp_path: Path):
    result = backup_service.create(tmp_path / "backup.db")
    assert result.integrity_check == "ok"
    assert result.sha256
    assert len(result.sha256) == 64
    assert Path(result.path).exists()
    assert result.size_bytes > 0


def test_online_backup_preserves_data(database: Database, backup_service: BackupService, tmp_path: Path):
    # Insert test data
    with database.connect() as conn:
        with conn.begin():
            conn.execute(
                text(
                    "INSERT INTO projects (id, name, team_identifier, created_at) "
                    "VALUES ('p-test-backup', 'Backup Project', 'team-1', '2026-01-01T00:00:00Z')"
                )
            )

    dest_file = tmp_path / "preserved.db"
    result = backup_service.create(dest_file)
    assert result.integrity_check == "ok"

    # Verify directly from backup file
    conn = sqlite3.connect(str(dest_file))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM projects WHERE id = 'p-test-backup'")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "Backup Project"
    conn.close()


def test_online_backup_default_path(backup_service: BackupService, tmp_path: Path):
    result = backup_service.create()
    assert result.integrity_check == "ok"
    backup_file = Path(result.path)
    assert backup_file.exists()
    assert backup_file.parent == tmp_path / "backups"
    assert backup_file.name.startswith("backup_")
    assert backup_file.suffix == ".db"


def test_admin_backup_api_route(client: TestClient, tmp_path: Path):
    custom_dest = tmp_path / "api_backup.db"
    response = client.post(
        "/api/v1/admin/backup",
        json={"destination": str(custom_dest)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["path"] == str(custom_dest)
    assert body["data"]["integrity_check"] == "ok"
    assert len(body["data"]["sha256"]) == 64
    assert custom_dest.exists()

    # Check sha256 matches actual file
    actual_hash = hashlib.sha256(custom_dest.read_bytes()).hexdigest()
    assert body["data"]["sha256"] == actual_hash


def test_admin_backup_api_default_destination(client: TestClient):
    response = client.post("/api/v1/admin/backup", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["integrity_check"] == "ok"
    assert Path(body["data"]["path"]).exists()
