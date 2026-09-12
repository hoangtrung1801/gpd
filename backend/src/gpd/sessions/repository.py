from datetime import datetime, timezone, timedelta
from typing import Sequence
import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, select, delete
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session

from gpd.db.models import Base, IdempotencyKey
from gpd.sessions.schemas import ChangedFile, CommitSummary, DeveloperSession, GitSnapshot


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_uuid() -> str:
    return str(uuid.uuid4())


class DeveloperSessionModel(Base):
    __tablename__ = "developer_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    repository_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    developer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    started_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)
    last_seen_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)
    completed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)

    files: Mapped[list["SessionFileModel"]] = relationship(
        "SessionFileModel", back_populates="session", cascade="all, delete-orphan"
    )
    commits: Mapped[list["SessionCommitModel"]] = relationship(
        "SessionCommitModel", back_populates="session", cascade="all, delete-orphan"
    )

    def to_schema(self) -> DeveloperSession:
        return DeveloperSession(
            id=self.id,
            project_id=self.project_id,
            task_id=self.task_id,
            repository_id=self.repository_id,
            developer=self.developer,
            agent=self.agent,
            branch=self.branch,
            status=self.status,
            started_at=self.started_at,
            last_seen_at=self.last_seen_at,
            completed_at=self.completed_at,
            created_at=self.created_at,
            changed_files=[ChangedFile(path=f.path, change_kind=f.change_kind) for f in self.files],
            commits=[
                CommitSummary(hash=c.commit_hash, message=c.message, authored_at=c.authored_at)
                for c in self.commits
            ],
        )


class SessionFileModel(Base):
    __tablename__ = "session_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("developer_sessions.id", ondelete="CASCADE"), nullable=False
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    change_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    observed_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)

    session: Mapped["DeveloperSessionModel"] = relationship("DeveloperSessionModel", back_populates="files")


class SessionCommitModel(Base):
    __tablename__ = "session_commits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("developer_sessions.id", ondelete="CASCADE"), nullable=False
    )
    commit_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    authored_at: Mapped[str | None] = mapped_column(Text, nullable=True)

    session: Mapped["DeveloperSessionModel"] = relationship("DeveloperSessionModel", back_populates="commits")


class SessionRepository:
    def create(
        self,
        session: Session,
        project_id: str,
        task_id: str | None = None,
        repository_id: str | None = None,
        developer: str | None = None,
        agent: str | None = None,
        branch: str | None = None,
        changed_files: Sequence[ChangedFile] | None = None,
        commits: Sequence[CommitSummary] | None = None,
    ) -> DeveloperSessionModel:
        now = utc_now_iso()
        model = DeveloperSessionModel(
            id=new_uuid(),
            project_id=project_id,
            task_id=task_id,
            repository_id=repository_id,
            developer=developer,
            agent=agent,
            branch=branch,
            status="active",
            started_at=now,
            last_seen_at=now,
            created_at=now,
        )
        session.add(model)
        session.flush()

        if changed_files:
            for f in changed_files:
                session.add(
                    SessionFileModel(
                        id=new_uuid(),
                        session_id=model.id,
                        path=f.path,
                        change_kind=f.change_kind,
                        observed_at=now,
                    )
                )

        if commits:
            for c in commits:
                session.add(
                    SessionCommitModel(
                        id=new_uuid(),
                        session_id=model.id,
                        commit_hash=c.hash,
                        message=c.message,
                        authored_at=c.authored_at,
                    )
                )

        session.flush()
        return model

    def get_by_id(self, session: Session, session_id: str) -> DeveloperSessionModel | None:
        return session.execute(
            select(DeveloperSessionModel).where(DeveloperSessionModel.id == session_id)
        ).scalar_one_or_none()

    def list_sessions(
        self,
        session: Session,
        project_id: str | None = None,
        task_id: str | None = None,
        status: str | None = None,
    ) -> list[DeveloperSessionModel]:
        stmt = select(DeveloperSessionModel)
        if project_id:
            stmt = stmt.where(DeveloperSessionModel.project_id == project_id)
        if task_id:
            stmt = stmt.where(DeveloperSessionModel.task_id == task_id)
        if status:
            stmt = stmt.where(DeveloperSessionModel.status == status)
        return list(session.execute(stmt.order_by(DeveloperSessionModel.created_at.desc())).scalars().all())

    def update_heartbeat(
        self,
        session: Session,
        session_id: str,
        changed_files: Sequence[ChangedFile] | None = None,
    ) -> DeveloperSessionModel | None:
        model = self.get_by_id(session, session_id)
        if not model:
            return None
        now = utc_now_iso()
        model.last_seen_at = now
        if model.status == "stale":
            model.status = "active"

        if changed_files is not None:
            # Replace file observations with fresh set
            session.execute(delete(SessionFileModel).where(SessionFileModel.session_id == session_id))
            for f in changed_files:
                session.add(
                    SessionFileModel(
                        id=new_uuid(),
                        session_id=session_id,
                        path=f.path,
                        change_kind=f.change_kind,
                        observed_at=now,
                    )
                )
        session.flush()
        return model

    def mark_stale_sessions(self, session: Session, expiry_seconds: int = 120) -> int:
        threshold = (datetime.now(timezone.utc) - timedelta(seconds=expiry_seconds)).isoformat()
        models = session.execute(
            select(DeveloperSessionModel).where(
                DeveloperSessionModel.status == "active",
                DeveloperSessionModel.last_seen_at < threshold,
            )
        ).scalars().all()
        for m in models:
            m.status = "stale"
        session.flush()
        return len(models)

    def get_idempotency_key(self, session: Session, endpoint: str, key: str) -> IdempotencyKey | None:
        return session.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.endpoint == endpoint,
                IdempotencyKey.key == key,
            )
        ).scalar_one_or_none()

    def save_idempotency_key(
        self,
        session: Session,
        endpoint: str,
        key: str,
        request_hash: str,
        status_code: int,
        response_body: str,
    ) -> IdempotencyKey:
        entry = IdempotencyKey(
            endpoint=endpoint,
            key=key,
            request_hash=request_hash,
            response_status=status_code,
            response_body=response_body,
            created_at=utc_now_iso(),
        )
        session.add(entry)
        session.flush()
        return entry
