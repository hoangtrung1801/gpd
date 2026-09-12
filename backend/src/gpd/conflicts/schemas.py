from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from gpd.sessions.schemas import ConflictEvidenceSchema


class ConflictResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    type: str  # work_overlap, contradictory_knowledge
    severity: str  # high, medium, low
    status: str  # active, resolved, dismissed
    explanation: str
    detector_version: str
    resolution_action: str | None = None
    resolved_by: str | None = None
    resolution_note: str | None = None
    resolved_at: str | None = None
    created_at: str
    updated_at: str
    evidence: list[ConflictEvidenceSchema] = Field(default_factory=list)


class ResolveConflictRequest(BaseModel):
    action: Literal["supersede", "clarify_scope", "accept_conditional", "dismiss"]
    actor: str = Field(min_length=1)
    note: str = Field(min_length=1)
    winner_id: str | None = None
    clarified_title: str | None = None
    clarified_content: str | None = None
