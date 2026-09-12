import asyncio
import json
import pytest
from sqlalchemy import text

from gpd.audit.service import append as append_audit
from gpd.db.engine import Database


def test_database_enables_required_pragmas(database: Database):
    with database.connect() as connection:
        journal_mode = connection.exec_driver_sql("PRAGMA journal_mode").scalar()
        assert journal_mode is not None
        assert journal_mode.lower() == "wal"

        foreign_keys = connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
        assert foreign_keys == 1

        busy_timeout = connection.exec_driver_sql("PRAGMA busy_timeout").scalar()
        assert busy_timeout == 5000


@pytest.mark.asyncio
async def test_database_write_serialization(database: Database):
    # Test concurrent writes serialize without database is locked errors
    def _write_item(val: int):
        with database.connect() as conn:
            with conn.begin():
                conn.execute(
                    text(
                        "INSERT INTO audit_events (id, actor, action, target, metadata, created_at) "
                        "VALUES (:id, :actor, :action, :target, :metadata, :created_at)"
                    ),
                    {
                        "id": f"event-{val}",
                        "actor": "tester",
                        "action": "test.write",
                        "target": f"item:{val}",
                        "metadata": json.dumps({"val": val}),
                        "created_at": "2026-09-12T00:00:00Z",
                    },
                )
        return val

    results = await asyncio.gather(*[database.write(_write_item, i) for i in range(20)])
    assert sorted(results) == list(range(20))

    with database.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM audit_events WHERE action = 'test.write'")
        ).scalar()
        assert count == 20


def test_audit_append_helper(database: Database):
    with database.connect() as conn:
        with conn.begin():
            event = append_audit(
                conn,
                "alice",
                "create.item",
                "target:42",
                {"reason": "testing"},
            )
            assert event.id is not None
            assert event.actor == "alice"
            assert event.action == "create.item"
            assert event.target == "target:42"

    with database.connect() as conn:
        row = conn.execute(
            text("SELECT actor, action, target, metadata FROM audit_events WHERE id = :id"),
            {"id": event.id},
        ).fetchone()

        assert row is not None
        assert row[0] == "alice"
        assert row[1] == "create.item"
        assert row[2] == "target:42"
        meta = json.loads(row[3])
        assert meta == {"reason": "testing"}
