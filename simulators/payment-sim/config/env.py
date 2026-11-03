from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def read_secret(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


class Env(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    secret_key_file: Path
    debug: bool = False
    allowed_hosts: list[str] = ["localhost"]
    sim_db_path: Path
    service_token_file: Path
    sim_slow_seconds: float = 4.0


env = Env()  # type: ignore[call-arg]  # values come from the environment, validated at startup
