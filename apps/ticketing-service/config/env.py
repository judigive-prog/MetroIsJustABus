"""The only place that reads the environment (conventions.md: configuration)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def read_secret(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


class Env(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    secret_key_file: Path
    debug: bool = False
    allowed_hosts: list[str] = ["localhost"]

    postgres_host: str
    postgres_port: int = 5432
    postgres_db: str
    postgres_user: str
    postgres_password_file: Path

    jwt_public_key_file: Path
    jwt_issuer: str | None = None

    payment_sim_url: str
    payment_sim_token_file: Path

    purchase_lease_seconds: int = 30
    purchase_retry_after_seconds: int = 5


env = Env()  # type: ignore[call-arg]  # values come from the environment, validated at startup
