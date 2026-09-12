from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Strictly ordered section list per architecture specification
SECTION_ORDER = [
    "task",
    "expected_actual",
    "discussion",
    "requirements_decisions",
    "files",
    "work_warnings",
    "contradictions",
    "background",
]


class CandidateEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    section: str
    content: str
    source_id: str | None = None
    knowledge_id: str | None = None
    score: float | None = None
    score_components: dict[str, float] | None = None
    selection_reason: str | None = None
    token_estimate: int
    is_mandatory: bool = False


class ContextEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    section: str
    content: str
    source_id: str | None = None
    knowledge_id: str | None = None
    score: float | None = None
    score_components: dict[str, float] | None = None
    selection_reason: str | None = None
    rank: int
    token_estimate: int


class ContextPackage(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    session_id: str | None = None
    task_id: str | None = None
    developer_query: str | None = None
    token_budget: int
    estimated_tokens: int
    renderer_version: str = "1.0"
    search_health_snapshot: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    entries: list[ContextEntry] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now_iso)

    @property
    def entry_ids(self) -> list[str]:
        return [e.id for e in self.entries]


class ContextRequest(BaseModel):
    project_id: str
    session_id: str | None = None
    task_id: str | None = None
    developer_prompt: str | None = None
    token_budget: int = 1500
    task_title: str | None = None
    task_description: str | None = None
    actual_behavior: str | None = None
    expected_behavior: str | None = None
    high_conflicts: list[str] | None = None
    lexical_available: bool = True
    vector_available: bool = True
