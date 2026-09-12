from typing import Any, Protocol, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LlmStructuredRequest(BaseModel):
    workflow: str
    prompt: str
    schema_version: str = "1.0"
    model: str = "default"
    provider: str = "fake"
    source_references: list[str] = []


class LlmStructuredResponse(BaseModel):
    data: Any
    input_tokens: int = 100
    output_tokens: int = 50
    model: str = "fake-model"
    provider: str = "fake-provider"


class LlmGateway(Protocol):
    async def generate_structured(
        self, request: LlmStructuredRequest, output_type: type[T]
    ) -> tuple[T, LlmStructuredResponse]:
        ...
