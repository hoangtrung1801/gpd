from dataclasses import dataclass, field
import re
from typing import Any

# Common secret patterns
OPENAI_KEY_RE = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{10,}\b")
SLACK_TOKEN_RE = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{8,}\b")
GITHUB_TOKEN_RE = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9_]{16,}|github_pat_[A-Za-z0-9_]{20,})\b"
)
PEM_BLOCK_RE = re.compile(
    r"-----BEGIN[ A-Z0-9_-]*PRIVATE KEY-----[\s\S]+?-----END[ A-Z0-9_-]*PRIVATE KEY-----"
)
AUTH_HEADER_RE = re.compile(
    r"(?i)\bauthorization:\s*(?:bearer|basic)\s+[A-Za-z0-9._~+/-]+=*"
)
DOTENV_SECRET_RE = re.compile(
    r"(?im)^([ \t]*(?:[A-Z0-9_]*(?:SECRET|TOKEN|KEY|PASSWORD|AUTH|PRIVATE)[A-Z0-9_]*)[ \t]*=[ \t]*)(['\"]?)(?!\s*\[REDACTED\])(.+?)\2[ \t]*$"
)

DEFAULT_SECRET_PATTERNS: list[re.Pattern[str]] = [
    PEM_BLOCK_RE,
    OPENAI_KEY_RE,
    SLACK_TOKEN_RE,
    GITHUB_TOKEN_RE,
    AUTH_HEADER_RE,
]


@dataclass
class RedactionResult:
    text: str
    redaction_count: int = 0
    matches: list[str] = field(default_factory=list)


class Redactor:
    def __init__(self, patterns: list[str | re.Pattern[str]] | None = None):
        self.custom_patterns: list[re.Pattern[str]] = []
        if patterns:
            for p in patterns:
                if isinstance(p, str):
                    self.custom_patterns.append(re.compile(p))
                else:
                    self.custom_patterns.append(p)

    def redact(self, text: str) -> RedactionResult:
        if not text:
            return RedactionResult(text=text, redaction_count=0, matches=[])

        count = 0
        matches: list[str] = []
        result = text

        # 1. Custom patterns first
        for pat in self.custom_patterns:
            def _repl_custom(m: re.Match[str]) -> str:
                nonlocal count
                count += 1
                matched = m.group(0)
                matches.append(matched)
                return "[REDACTED]"

            result = pat.sub(_repl_custom, result)

        # 2. Default secret patterns (PEM, OpenAI, Slack, GitHub, Auth headers)
        for pat in DEFAULT_SECRET_PATTERNS:
            def _repl_default(m: re.Match[str]) -> str:
                nonlocal count
                count += 1
                matched = m.group(0)
                matches.append(matched)
                return "[REDACTED]"

            result = pat.sub(_repl_default, result)

        # 3. Dotenv secrets (replace value only)
        def _repl_dotenv(m: re.Match[str]) -> str:
            nonlocal count
            count += 1
            matched = m.group(3)
            matches.append(matched)
            prefix = m.group(1)
            quote = m.group(2)
            return f"{prefix}{quote}[REDACTED]{quote}"

        result = DOTENV_SECRET_RE.sub(_repl_dotenv, result)

        return RedactionResult(text=result, redaction_count=count, matches=matches)

    def redact_data(self, data: Any) -> Any:
        """Recursively redact strings in dicts, lists, and other structures."""
        if isinstance(data, str):
            return self.redact(data).text
        elif isinstance(data, dict):
            return {
                self.redact(str(k)).text if isinstance(k, str) else k: self.redact_data(v)
                for k, v in data.items()
            }
        elif isinstance(data, (list, tuple, set)):
            redacted_items = [self.redact_data(item) for item in data]
            if isinstance(data, tuple):
                return tuple(redacted_items)
            elif isinstance(data, set):
                return set(redacted_items)
            return redacted_items
        return data


default_redactor = Redactor()


def redact(text: str) -> RedactionResult:
    return default_redactor.redact(text)
