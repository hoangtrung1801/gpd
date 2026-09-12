from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class SourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1, max_length=64, description="Source type (prd, document, slack_thread, note)")
    title: str = Field(min_length=1, max_length=255, description="Source title")
    content: str = Field(min_length=1, description="Raw source content")
    canonical_ref: str | None = Field(default=None, max_length=1024, description="Repository-relative path or URL")
    author: str | None = Field(default=None, max_length=255, description="Author identifier or name")


class SourceSpanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    locator: str
    content: str
    checksum: str
    created_at: str


class SourceChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    locator: str | None
    chunk_text: str
    token_estimate: int
    created_at: str


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    type: str
    title: str
    canonical_ref: str | None = None
    author: str | None = None
    captured_at: str | None = None
    content_hash: str
    state: str
    error_message: str | None = None
    created_at: str
    updated_at: str


class SourceDetailResponse(SourceResponse):
    spans: list[SourceSpanResponse] = Field(default_factory=list)
    chunks: list[SourceChunkResponse] = Field(default_factory=list)


class SourceIngestResult(BaseModel):
    source_id: str
    job_id: str | None = None
    state: str
    reused: bool = False
    content_hash: str
