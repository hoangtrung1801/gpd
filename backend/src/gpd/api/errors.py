from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    fields: dict[str, list[str]] | None = None


class ApiEnvelope(BaseModel, Generic[T]):
    ok: bool
    data: T | None = None
    warnings: list[str] = Field(default_factory=list)
    error: ApiError | None = None


class ApiException(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        retryable: bool = False,
        fields: dict[str, list[str]] | None = None,
        warnings: list[str] | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.retryable = retryable
        self.fields = fields
        self.warnings = warnings or []
