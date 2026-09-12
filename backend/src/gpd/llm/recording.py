from collections import deque
from typing import Any, TypeVar
from pydantic import BaseModel

from gpd.llm.gateway import LlmGateway, LlmStructuredRequest, LlmStructuredResponse

T = TypeVar("T", bound=BaseModel)


class FakeLlmGateway(LlmGateway):
    def __init__(self) -> None:
        self.responses: deque[Any] = deque()
        self.requests: list[LlmStructuredRequest] = []

    def respond(self, payload: Any) -> None:
        self.responses.append(payload)

    async def generate_structured(
        self, request: LlmStructuredRequest, output_type: type[T]
    ) -> tuple[T, LlmStructuredResponse]:
        self.requests.append(request)
        if not self.responses:
            raise RuntimeError("FakeLlmGateway has no responses queued")

        raw = self.responses.popleft()
        if isinstance(raw, output_type):
            parsed = raw
        elif isinstance(raw, dict):
            parsed = output_type.model_validate(raw)
        else:
            parsed = output_type.model_validate(raw)

        meta = LlmStructuredResponse(
            data=parsed.model_dump(mode="json"),
            input_tokens=120,
            output_tokens=65,
            model="fake-llm-1",
            provider="fake",
        )
        return parsed, meta


class RecordingLlmGateway(FakeLlmGateway):
    pass
