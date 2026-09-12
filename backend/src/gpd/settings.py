import ipaddress
from pathlib import Path
from typing import Any
from pydantic import AliasChoices, Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class SettingsError(ValueError):
    """Raised when application settings are invalid."""
    pass


def is_loopback_host(host: str) -> bool:
    if host.lower() in ("localhost", "127.0.0.1", "::1", "testclient"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback
    except ValueError:
        return False
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GPD_",
        env_file=".env",
        extra="ignore",
    )

    database_path: Path = Field(
        default=Path(".gpd/gpd.db"),
        validation_alias=AliasChoices("database_path", "gpd_database_path"),
    )
    web_dist_path: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("web_dist_path", "gpd_web_dist_path"),
    )
    api_host: str = "127.0.0.1"
    api_port: int = 7337
    app_version: str = "0.1.0"

    access_token: SecretStr | None = None
    slack_signing_secret: SecretStr | None = None
    slack_bot_token: SecretStr | None = None

    llm_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"
    context_token_budget: int = 8000
    session_heartbeat_timeout_seconds: int = 120

    @model_validator(mode="after")
    def validate_access_token_for_non_loopback(self) -> "Settings":
        if not is_loopback_host(self.api_host):
            if not self.access_token or not self.access_token.get_secret_value().strip():
                raise SettingsError(
                    "Non-loopback binding requires an access token (GPD_ACCESS_TOKEN)"
                )
        return self

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        try:
            super().__init__(*args, **kwargs)
        except ValidationError as e:
            for err in e.errors():
                ctx = err.get("ctx", {})
                exc = ctx.get("error")
                if isinstance(exc, SettingsError):
                    raise exc
            raise
