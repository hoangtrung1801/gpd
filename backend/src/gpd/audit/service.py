import json
from typing import Any
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.engine import Connection

from gpd.db.models import AuditEvent, new_uuid, utc_now_iso
from gpd.security.redaction import default_redactor


def append(
    *args: Any,
    connection: Connection | None = None,
    session: Session | None = None,
    conn: Connection | None = None,
    **kwargs: Any,
) -> AuditEvent:
    """Append an audit event within an existing transaction.

    Supports multiple calling conventions:
      - append(actor, action, target, metadata=None, *, connection=...)
      - append(conn, actor, action, target, metadata=None)
      - append(session, actor, action, target, metadata=None)
    """
    target_conn: Connection | Session | None = connection or session or conn

    # Check if first positional arg is a connection/session
    first = args[0] if args else None
    if first is not None and (hasattr(first, "execute") or isinstance(first, (Connection, Session))):
        target_conn = first
        pos_args = args[1:]
    else:
        pos_args = args

    actor = pos_args[0] if len(pos_args) > 0 else kwargs.get("actor")
    action = pos_args[1] if len(pos_args) > 1 else kwargs.get("action")
    target = pos_args[2] if len(pos_args) > 2 else kwargs.get("target")
    metadata = pos_args[3] if len(pos_args) > 3 else kwargs.get("metadata")

    if not actor or not action or not target:
        raise ValueError("actor, action, and target are required for audit event")

    # Redact sensitive information before persistence
    actor = default_redactor.redact(actor).text
    action = default_redactor.redact(action).text
    target = default_redactor.redact(target).text

    metadata_str: str | None = None
    if metadata is not None:
        redacted_meta = default_redactor.redact_data(metadata)
        if isinstance(redacted_meta, str):
            metadata_str = redacted_meta
        else:
            metadata_str = json.dumps(redacted_meta)
    event_id = new_uuid()
    created_at = utc_now_iso()

    event = AuditEvent(
        id=event_id,
        actor=actor,
        action=action,
        target=target,
        metadata_json=metadata_str,
        created_at=created_at,
    )

    if target_conn is not None:
        if isinstance(target_conn, Session):
            target_conn.add(event)
            target_conn.flush()
        else:
            target_conn.execute(
                text(
                    "INSERT INTO audit_events (id, actor, action, target, metadata, created_at) "
                    "VALUES (:id, :actor, :action, :target, :metadata, :created_at)"
                ),
                {
                    "id": event_id,
                    "actor": actor,
                    "action": action,
                    "target": target,
                    "metadata": metadata_str,
                    "created_at": created_at,
                },
            )

    return event


class AuditService:
    def __init__(self, database: Any = None):
        self.database = database

    def append(
        self,
        actor: str,
        action: str,
        target: str,
        metadata: dict[str, Any] | None = None,
        *,
        connection: Connection | None = None,
        session: Session | None = None,
    ) -> AuditEvent:
        return append(
            actor,
            action,
            target,
            metadata,
            connection=connection,
            session=session,
        )

    def query(
        self,
        *,
        actor: str | None = None,
        action: str | None = None,
        target: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        if not self.database:
            return []
        with self.database.session() as session:
            stmt = session.query(AuditEvent)
            if actor:
                stmt = stmt.filter(AuditEvent.actor == actor)
            if action:
                stmt = stmt.filter(AuditEvent.action == action)
            if target:
                stmt = stmt.filter(AuditEvent.target == target)
            stmt = stmt.order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit)
            return list(stmt.all())

    def get(self, event_id: str) -> AuditEvent | None:
        if not self.database:
            return None
        with self.database.session() as session:
            return session.query(AuditEvent).filter(AuditEvent.id == event_id).first()
