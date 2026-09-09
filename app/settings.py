from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
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
    # Retell custom-function timeout is configured in milliseconds in the
    # dashboard (minimum 1000). The lab delay must exceed that value so the
    # first booking response is lost and Retell retries.
    retell_function_timeout_seconds: float = Field(default=2.0, gt=0)
    failure_lab_delay_seconds: float = Field(default=3.0, gt=0)

    @model_validator(mode="after")
    def delay_must_exceed_timeout(self) -> "Settings":
        if self.failure_lab_delay_seconds <= self.retell_function_timeout_seconds:
            raise ValueError(
                "FAILURE_LAB_DELAY_SECONDS must exceed RETELL_FUNCTION_TIMEOUT_SECONDS."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
