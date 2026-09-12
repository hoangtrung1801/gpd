import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

T = TypeVar("T")


class Database:
    def __init__(self, engine: Engine):
        self.engine = engine
        self._write_lock = asyncio.Lock()
        self.session_factory = sessionmaker(bind=self.engine)

    @classmethod
    def open(cls, path: Path) -> "Database":
        path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            "sqlite+pysqlite:///" + str(path),
            connect_args={"check_same_thread": False, "timeout": 5},
        )

        @event.listens_for(engine, "connect")
        def configure_sqlite(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        db = cls(engine)
        with db.engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        return db

    def connect(self):
        return self.engine.connect()

    def session(self) -> Session:
        return self.session_factory()

    async def write(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        async with self._write_lock:
            return await asyncio.to_thread(fn, *args, **kwargs)

    def close(self) -> None:
        self.engine.dispose()
