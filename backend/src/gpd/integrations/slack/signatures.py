from datetime import datetime, timezone
import hashlib
import hmac
from typing import Union
from pydantic import SecretStr

from gpd.api.errors import ApiException


class SlackSignatureInvalid(ApiException):
    def __init__(self, message: str = "Invalid Slack signature"):
        super().__init__(
            status_code=401,
            code="slack_signature_invalid",
            message=message,
            retryable=False,
        )


class SlackReplayRejected(ApiException):
    def __init__(self, message: str = "Slack replay rejected: timestamp outside 300s window"):
        super().__init__(
            status_code=401,
            code="slack_replay_rejected",
            message=message,
            retryable=False,
        )


def verify_slack_signature(
    signing_secret: Union[SecretStr, str],
    timestamp: str,
    raw_body: bytes,
    signature: str,
    now: datetime | None = None,
) -> None:
    current_time = now or datetime.now(timezone.utc)

    try:
        ts_val = int(timestamp)
    except (ValueError, TypeError):
        raise SlackReplayRejected("Invalid timestamp format")

    if abs(current_time.timestamp() - ts_val) > 300:
        raise SlackReplayRejected("Slack timestamp outside 300s replay window")

    secret_str = (
        signing_secret.get_secret_value()
        if isinstance(signing_secret, SecretStr)
        else str(signing_secret)
    )

    base = b"v0:" + str(ts_val).encode("utf-8") + b":" + raw_body
    computed = "v0=" + hmac.new(
        secret_str.encode("utf-8"), base, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed, signature):
        raise SlackSignatureInvalid("Slack signature does not match computed digest")
