from typing import Literal
from pydantic import BaseModel, Field


class Claim(BaseModel):
    id: str
    project_id: str
    title: str
    content: str
    evidence_ids: list[str] = Field(default_factory=list)
    type: str = "decision"


class ContradictionResult(BaseModel):
    classification: Literal["compatible", "superseding", "ambiguous", "contradictory"]
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str = Field(min_length=1, max_length=1_000)
    evidence_ids: list[str] = Field(min_length=2)
