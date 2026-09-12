from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChangedFile(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    path: str
    change_kind: str  # modified, added, deleted, untracked, renamed


class CommitSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    hash: str
    message: str
    authored_at: str | None = None


class GitSnapshot(BaseModel):
    # root is transient only - never persisted in DB
    root: Path | None = None
    branch: str = ""
    changed_files: list[ChangedFile] = Field(default_factory=list)
    recent_commits: list[CommitSummary] = Field(default_factory=list)
    remote_url: str | None = None


class ConflictEvidenceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    kind: str
    target_type: str
    target_id: str
    score_component: float | None = None
    detail: str | None = None


class OverlapWarning(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    severity: str  # high, medium, low
    score: float
    explanation: str
    suggested_action: str
    evidence: list[ConflictEvidenceSchema] = Field(default_factory=list)
    conflicting_session_id: str | None = None


class DeveloperSession(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    task_id: str | None = None
    repository_id: str | None = None
    developer: str | None = None
    agent: str | None = None
    branch: str | None = None
    status: str = "active"  # active, stale, analyzing, completed, abandoned
    started_at: str
    last_seen_at: str
    completed_at: str | None = None
    created_at: str
    changed_files: list[ChangedFile] = Field(default_factory=list)
    commits: list[CommitSummary] = Field(default_factory=list)
    is_replay: bool = False


class StartSessionRequest(BaseModel):
    project_id: str
    task_id: str | None = None
    repository_id: str | None = None
    developer: str | None = None
    agent: str | None = None
    repo_path: str | None = None
    changed_files: list[ChangedFile] | None = None


class StartSessionResponse(BaseModel):
    session: DeveloperSession
    warnings: list[OverlapWarning] = Field(default_factory=list)


class HeartbeatRequest(BaseModel):
    repo_path: str | None = None
    changed_files: list[ChangedFile] | None = None


class FinishSessionRequest(BaseModel):
    agent_summary: str | None = Field(default=None, max_length=10_000)
    diff: str | None = Field(default=None, max_length=20_000)


class FinishSessionResponse(BaseModel):
    session: DeveloperSession
    job: dict[str, Any] | None = None
    proposals: list[Any] = Field(default_factory=list)
