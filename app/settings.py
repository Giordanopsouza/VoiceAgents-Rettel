from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_path: Path = Path("data/calendar.sqlite")
    live_demo_enabled: bool = False
    retell_api_key: str = ""
    retell_agent_id: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
