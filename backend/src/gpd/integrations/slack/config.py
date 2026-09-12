import os
from pydantic import SecretStr


def get_slack_signing_secret(request=None) -> SecretStr | None:
    # If env var is explicitly deleted or empty, and request settings exist, check if settings got it from dotenv
    env_val = os.getenv("GPD_SLACK_SIGNING_SECRET")
    if env_val is None:
        env_val = os.getenv("SLACK_SIGNING_SECRET")
    if env_val is not None:
        return SecretStr(env_val) if env_val else None
    if request and hasattr(request.app.state, "settings"):
        sec = getattr(request.app.state.settings, "slack_signing_secret", None)
        if sec:
            return sec if isinstance(sec, SecretStr) else SecretStr(str(sec))
    return None


def get_slack_bot_token(request=None) -> SecretStr | None:
    env_val = os.getenv("GPD_SLACK_BOT_TOKEN")
    if env_val is None:
        env_val = os.getenv("SLACK_BOT_TOKEN")
    if env_val is not None:
        return SecretStr(env_val) if env_val else None
    if request and hasattr(request.app.state, "settings"):
        tok = getattr(request.app.state.settings, "slack_bot_token", None)
        if tok:
            return tok if isinstance(tok, SecretStr) else SecretStr(str(tok))
    return None
