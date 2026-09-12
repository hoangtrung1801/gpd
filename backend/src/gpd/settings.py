from pathlib import Path
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GPD_",
        env_file=".env",
        extra="ignore",
    )

    database_path: Path = Path(".gpd/gpd.db")
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
