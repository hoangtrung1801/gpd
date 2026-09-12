from typing import Any, Generic, Literal, TypeVar
from pydantic import BaseModel, Field, field_validator

from gpd.llm.gateway import LlmGateway, LlmStructuredRequest

T = TypeVar("T")


class InvalidEvidenceReference(Exception):
    pass


class EvidenceRef(BaseModel):
    message_id: str


class ExtractedField(BaseModel, Generic[T]):
    value: T | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[EvidenceRef] = Field(default_factory=list)

    @field_validator("evidence", mode="before")
    @classmethod
    def normalize_evidence(cls, v: Any) -> list[Any]:
        if isinstance(v, list):
            normalized: list[Any] = []
            for item in v:
                if isinstance(item, str):
                    normalized.append({"message_id": item})
                elif isinstance(item, dict) and "message_id" in item:
                    normalized.append(item)
                elif isinstance(item, EvidenceRef):
                    normalized.append(item)
                else:
                    normalized.append(item)
            return normalized
        return v


class BugExtraction(BaseModel):
    title: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str]())
    summary: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str]())
    description: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str]())
    reproduction_steps: ExtractedField[list[str]] = Field(
        default_factory=lambda: ExtractedField[list[str]]()
    )
    actual_behavior: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str]())
    expected_behavior: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str]())
    environment: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str]())
    severity: ExtractedField[Literal["low", "medium", "high", "critical"]] = Field(
        default_factory=lambda: ExtractedField[Literal["low", "medium", "high", "critical"]]()
    )
    affected_component: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str]())
    technical_clues: ExtractedField[list[str]] = Field(
        default_factory=lambda: ExtractedField[list[str]]()
    )
    participants: list[str] = Field(default_factory=list)
    acceptance_criteria: ExtractedField[str] | None = None


def extract_thread_message_ids(thread: Any) -> set[str]:
    ids: set[str] = set()
    messages: list[Any] = []
    if hasattr(thread, "messages"):
        messages = thread.messages or []
    elif isinstance(thread, dict) and "messages" in thread:
        messages = thread["messages"] or []
    elif isinstance(thread, list):
        messages = thread

    for msg in messages:
        if isinstance(msg, dict):
            for k in ("external_message_id", "id", "ts", "message_id"):
                if msg.get(k):
                    ids.add(str(msg[k]))
        else:
            for k in ("external_message_id", "id", "ts", "message_id"):
                val = getattr(msg, k, None)
                if val is not None:
                    ids.add(str(val))
    return ids


class BugExtractionWorkflow:
    def __init__(self, llm: LlmGateway):
        self.llm = llm

    def _validate_extraction(
        self, extraction: BugExtraction, valid_ids: set[str]
    ) -> list[str]:
        errors: list[str] = []

        if not extraction.title.value or not extraction.title.value.strip():
            errors.append("Title must be a nonempty string")
        if not extraction.description.value or not extraction.description.value.strip():
            errors.append("Description must be a nonempty string")

        # Check evidence across all fields
        fields_to_check = [
            extraction.title,
            extraction.summary,
            extraction.description,
            extraction.reproduction_steps,
            extraction.actual_behavior,
            extraction.expected_behavior,
            extraction.environment,
            extraction.severity,
            extraction.affected_component,
            extraction.technical_clues,
        ]
        if extraction.acceptance_criteria:
            fields_to_check.append(extraction.acceptance_criteria)

        for f in fields_to_check:
            for ev in f.evidence:
                if ev.message_id not in valid_ids:
                    errors.append(f"Invalid evidence reference: '{ev.message_id}' not in thread")

        return errors

    async def extract(self, thread: Any) -> BugExtraction:
        valid_ids = extract_thread_message_ids(thread)
        req = LlmStructuredRequest(
            workflow="bug_extraction",
            prompt="Extract evidence-backed bug from conversation thread",
            schema_version="1.0",
        )

        extraction, _ = await self.llm.generate_structured(req, BugExtraction)
        errors = self._validate_extraction(extraction, valid_ids)

        if errors:
            # 1 corrective retry
            has_evidence_err = any("Invalid evidence reference" in e for e in errors)
            retry_req = LlmStructuredRequest(
                workflow="bug_extraction",
                prompt=f"Validation failed: {', '.join(errors)}. Re-extract using ONLY valid message IDs: {list(valid_ids)}",
                schema_version="1.0",
            )
            try:
                extraction, _ = await self.llm.generate_structured(retry_req, BugExtraction)
                retry_errors = self._validate_extraction(extraction, valid_ids)
                if retry_errors:
                    if any("Invalid evidence reference" in e for e in retry_errors):
                        raise InvalidEvidenceReference(
                            f"Evidence references message_id outside thread: {retry_errors}"
                        )
                    raise ValueError(f"Bug extraction validation failed: {retry_errors}")
            except InvalidEvidenceReference:
                raise
            except Exception as exc:
                if has_evidence_err:
                    raise InvalidEvidenceReference(f"Evidence references message_id outside thread: {errors}") from exc
                raise

        return extraction
