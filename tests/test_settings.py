from pathlib import Path

import pytest
from pydantic import ValidationError

from app.settings import Settings


def test_settings_use_safe_defaults_without_env_file():
    settings = Settings(_env_file=None)

    assert settings.database_path == Path("data/calendar.sqlite")
    assert settings.live_demo_enabled is False
    assert settings.retell_api_key == ""
    assert settings.retell_agent_id == ""
    assert settings.retell_function_timeout_seconds == 2.0
    assert settings.failure_lab_delay_seconds == 3.0


def test_settings_load_values_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", "/tmp/demo.sqlite")
    monkeypatch.setenv("LIVE_DEMO_ENABLED", "true")
    monkeypatch.setenv("RETELL_API_KEY", "test-key")
    monkeypatch.setenv("RETELL_AGENT_ID", "agent_test")
    monkeypatch.setenv("RETELL_FUNCTION_TIMEOUT_SECONDS", "1.5")
    monkeypatch.setenv("FAILURE_LAB_DELAY_SECONDS", "2.5")

    settings = Settings(_env_file=None)

    assert settings.database_path == Path("/tmp/demo.sqlite")
    assert settings.live_demo_enabled is True
    assert settings.retell_api_key == "test-key"
    assert settings.retell_agent_id == "agent_test"
    assert settings.retell_function_timeout_seconds == 1.5
    assert settings.failure_lab_delay_seconds == 2.5


def test_settings_reject_delay_that_does_not_exceed_timeout():
    with pytest.raises(ValidationError):
        Settings(
            retell_function_timeout_seconds=2.0,
            failure_lab_delay_seconds=2.0,
            _env_file=None,
        )
