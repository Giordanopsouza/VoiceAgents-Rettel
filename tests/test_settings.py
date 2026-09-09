from pathlib import Path

from app.settings import Settings


def test_settings_use_safe_defaults_without_env_file():
    settings = Settings(_env_file=None)

    assert settings.database_path == Path("data/calendar.sqlite")
    assert settings.live_demo_enabled is False
    assert settings.retell_api_key == ""
    assert settings.retell_agent_id == ""


def test_settings_load_values_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", "/tmp/demo.sqlite")
    monkeypatch.setenv("LIVE_DEMO_ENABLED", "true")
    monkeypatch.setenv("RETELL_API_KEY", "test-key")
    monkeypatch.setenv("RETELL_AGENT_ID", "agent_test")

    settings = Settings(_env_file=None)

    assert settings.database_path == Path("/tmp/demo.sqlite")
    assert settings.live_demo_enabled is True
    assert settings.retell_api_key == "test-key"
    assert settings.retell_agent_id == "agent_test"
