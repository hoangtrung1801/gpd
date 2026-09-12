import re
from typing import Sequence
from pydantic import BaseModel, Field

from gpd.sessions.schemas import ChangedFile, CommitSummary

SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_\-]{10,}", re.IGNORECASE),
    re.compile(r"(api[_-]?key|api[_-]?token|secret[_-]?key|access[_-]?token|auth[_-]?token|password)\s*[:=]\s*['\"][^'\"]+['\"]", re.IGNORECASE),
    re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{15,}", re.IGNORECASE),
]


def sanitize_diff(diff: str, max_length: int = 20_000) -> str:
    if not diff:
        return ""

    sanitized = diff

    # Exclude binary diffs
    lines = [line for line in sanitized.splitlines() if not line.startswith("Binary files ")]
    sanitized = "\n".join(lines)

    # Redact secret patterns
    for pat in SECRET_PATTERNS:
        sanitized = pat.sub("[REDACTED]", sanitized)

    # Bound length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "\n... [diff truncated]"

    return sanitized


class CompletionInput(BaseModel):
    task_id: str
    context_package_id: str | None = None
    changed_files: list[ChangedFile] = Field(default_factory=list)
    diff_summary: str = Field(default="", max_length=20_000)
    commits: list[CommitSummary] = Field(default_factory=list)
    agent_summary: str | None = Field(default=None, max_length=10_000)
