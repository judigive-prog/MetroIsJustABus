"""The only place that reads the environment for core-backend (conventions.md: configuration)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def read_secret(path: Path | None, default: str = "") -> str:
    if path and path.exists():
        return path.read_text(encoding="utf-8").strip()
    return default


class Env(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=(".env", ".env.test"),
        env_file_encoding="utf-8",
    )

    secret_key_file: Path | None = None
    debug: bool = False
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "core-backend"]

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "test_core"
    postgres_user: str = "postgres"
    postgres_password_file: Path | None = None

    jwt_private_key_file: Path | None = None
    jwt_public_key_file: Path | None = None
    jwt_issuer: str | None = None
    jwt_access_ttl_seconds: int = 3600
    jwt_key_id: str = "core-rs256-v1"


env = Env()  # type: ignore[call-arg]  # values come from the environment, validated at startup
