from datetime import datetime, timezone
import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

try:
    from gpd.db.models import Base, new_uuid, utc_now_iso
except ImportError:
    def utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def new_uuid() -> str:
        return str(uuid.uuid4())

    class Base(DeclarativeBase):  # type: ignore[no-redef]
        pass


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_jobs_idempotency_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_expires_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)
    completed_at: Mapped[str | None] = mapped_column(Text, nullable=True)

    job_attempts: Mapped[list["JobAttempt"]] = relationship(
        "JobAttempt", back_populates="job", cascade="all, delete-orphan"
    )


class JobAttempt(Base):
    __tablename__ = "job_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)
    finished_at: Mapped[str | None] = mapped_column(Text, nullable=True)

    job: Mapped["Job"] = relationship("Job", back_populates="job_attempts")
