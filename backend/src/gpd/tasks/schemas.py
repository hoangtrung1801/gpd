from typing import Literal
from pydantic import BaseModel, Field


class TaskBase(BaseModel):
    title: str
    description: str
    type: str = "bug"
    status: str = "open"
    priority: str = "medium"
    reporter: str | None = None
    assignee: str | None = None
    component: str | None = None
    acceptance_criteria: str | None = None


class TaskSummary(BaseModel):
    id: str
    public_id: str
    type: str
    title: str
    status: str
    priority: str
    component: str | None = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class TaskDetail(BaseModel):
    id: str
    public_id: str
    type: str
    title: str
    description: str
    status: str
    priority: str
    reporter: str | None = None
    assignee: str | None = None
    component: str | None = None
    acceptance_criteria: str | None = None
    created_at: str
    updated_at: str

    # Bug specific fields
    summary: str | None = None
    reproduction_steps: list[str] | None = None
    actual_behavior: str | None = None
    expected_behavior: str | None = None
    environment: str | None = None
    severity: str | None = None
    affected_component: str | None = None
    technical_clues: list[str] | None = None
    participants: list[str] = Field(default_factory=list)

    # Relationships
    task_files: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    knowledge_ids: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}
