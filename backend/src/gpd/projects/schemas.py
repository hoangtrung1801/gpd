from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class Repository(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    root_path: str
    remote_url: str | None = None
    default_branch: str = "main"


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    team_identifier: str | None = Field(default=None, max_length=120)
    repository_root: str
    remote_url: str | None = None
    default_branch: str = "main"


class Project(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")

    id: UUID
    name: str
    team_identifier: str | None = None
    created_at: datetime
    repositories: list[Repository] = Field(default_factory=list)
    is_replay: bool = Field(default=False, exclude=True)
