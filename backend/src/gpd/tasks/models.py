from datetime import datetime, timezone
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gpd.db.models import Base, new_uuid, utc_now_iso


class PublicIdCounter(Base):
    __tablename__ = "public_id_counters"

    prefix: Mapped[str] = mapped_column(String(32), primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    type: Mapped[str] = mapped_column(String(64), default="bug", nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="open", nullable=False)
    priority: Mapped[str] = mapped_column(String(64), default="medium", nullable=False)
    reporter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    assignee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    component: Mapped[str | None] = mapped_column(String(255), nullable=True)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)

    bug_details: Mapped["BugDetails | None"] = relationship(
        "BugDetails", back_populates="task", uselist=False, cascade="all, delete-orphan"
    )
    task_sources: Mapped[list["TaskSource"]] = relationship(
        "TaskSource", back_populates="task", cascade="all, delete-orphan"
    )
    task_knowledge: Mapped[list["TaskKnowledge"]] = relationship(
        "TaskKnowledge", back_populates="task", cascade="all, delete-orphan"
    )
    task_files: Mapped[list["TaskFile"]] = relationship(
        "TaskFile", back_populates="task", cascade="all, delete-orphan"
    )


class BugDetails(Base):
    __tablename__ = "bug_details"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reproduction_steps: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual_behavior: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_behavior: Mapped[str | None] = mapped_column(Text, nullable=True)
    environment: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    affected_component: Mapped[str | None] = mapped_column(String(255), nullable=True)
    technical_clues: Mapped[str | None] = mapped_column(Text, nullable=True)
    participants: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)

    task: Mapped["Task"] = relationship("Task", back_populates="bug_details")


class TaskSource(Base):
    __tablename__ = "task_sources"

    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    source_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    relationship_type: Mapped[str] = mapped_column(
        "relationship", String(64), default="source", nullable=False
    )
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)

    task: Mapped["Task"] = relationship("Task", back_populates="task_sources")


class TaskKnowledge(Base):
    __tablename__ = "task_knowledge"

    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    knowledge_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    relationship_type: Mapped[str] = mapped_column(
        "relationship", String(64), default="context", nullable=False
    )
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)

    task: Mapped["Task"] = relationship("Task", back_populates="task_knowledge")


class TaskFile(Base):
    __tablename__ = "task_files"

    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    file_path: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)

    task: Mapped["Task"] = relationship("Task", back_populates="task_files")


class LlmRun(Base):
    __tablename__ = "llm_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    workflow: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_references: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    state: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_errors: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now_iso, nullable=False)
