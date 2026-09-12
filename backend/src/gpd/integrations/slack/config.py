import os
from pydantic import SecretStr


def get_slack_signing_secret(request=None) -> SecretStr | None:
    if request and hasattr(request.app.state, "settings"):
        sec = getattr(request.app.state.settings, "slack_signing_secret", None)
        if sec:
            return sec if isinstance(sec, SecretStr) else SecretStr(str(sec))
    env_val = os.getenv("GPD_SLACK_SIGNING_SECRET") or os.getenv("SLACK_SIGNING_SECRET")
    if env_val:
        return SecretStr(env_val)
    return None


def get_slack_bot_token(request=None) -> SecretStr | None:
    if request and hasattr(request.app.state, "settings"):
        tok = getattr(request.app.state.settings, "slack_bot_token", None)
        if tok:
            return tok if isinstance(tok, SecretStr) else SecretStr(str(tok))
    env_val = os.getenv("GPD_SLACK_BOT_TOKEN") or os.getenv("SLACK_BOT_TOKEN")
    if env_val:
        return SecretStr(env_val)
    return None
