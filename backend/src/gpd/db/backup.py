from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
import uuid

from gpd.db.engine import Database


@dataclass
class BackupResult:
    path: str
    sha256: str
    integrity_check: str
    size_bytes: int = 0
    created_at: str = ""


class BackupService:
    def __init__(self, database: Database, backup_dir: Path | None = None):
        self.database = database
        self.backup_dir = backup_dir or Path(".gpd/backups")

    def create(self, dest_path: Path | None = None) -> BackupResult:
        if dest_path is None:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            dest_path = self.backup_dir / f"backup_{timestamp}_{uuid.uuid4().hex[:8]}.db"
        else:
            dest_path = Path(dest_path)
            dest_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Online backup via sqlite3.Connection.backup
        with self.database.connect() as conn:
            raw_conn = getattr(conn.connection, "dbapi_connection", conn.connection)
            dest_conn = sqlite3.connect(str(dest_path))
            try:
                raw_conn.backup(dest_conn)
            finally:
                dest_conn.close()

        # 2. PRAGMA integrity_check
        check_conn = sqlite3.connect(str(dest_path))
        try:
            cursor = check_conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            row = cursor.fetchone()
            integrity_status = row[0] if row else "unknown"
        finally:
            check_conn.close()

        # 3. SHA-256 checksum
        hasher = hashlib.sha256()
        with open(dest_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        checksum = hasher.hexdigest()

        stat = dest_path.stat()
        created_at = datetime.now(timezone.utc).isoformat()

        return BackupResult(
            path=str(dest_path),
            sha256=checksum,
            integrity_check=integrity_status,
            size_bytes=stat.st_size,
            created_at=created_at,
        )
