import pytest

from src.config import Config, ConfigurationError, load_config


REQUIRED_STRINGS = {
    "GOOGLE_CLIENT_ID": "test-google-client-id",
    "GEMINI_API_KEY": "test-gemini-api-key",
    "GEMINI_MODEL": "gemini-3.5-flash-lite",
    "DYNAMODB_TABLE_NAME": "test-dynamodb-table",
    "SESSION_HMAC_SECRET": "test-session-hmac-secret",
}

REQUIRED_INTS = {
    "MAX_MESSAGE_LENGTH": "100",
    "MAX_REQUEST_BYTES": "2048",
    "USER_DAILY_LIMIT": "10",
    "GLOBAL_HOURLY_LIMIT": "50",
    "GLOBAL_DAILY_LIMIT": "200",
    "GEMINI_TIMEOUT_SECONDS": "30",
}

ALL_REQUIRED = {**REQUIRED_STRINGS, **REQUIRED_INTS}


def set_valid_env(monkeypatch) -> None:
    for name, value in ALL_REQUIRED.items():
        monkeypatch.setenv(name, value)


def clear_config_env(monkeypatch) -> None:
    for name in ALL_REQUIRED:
        monkeypatch.delenv(name, raising=False)


def test_load_config_with_valid_environment(monkeypatch):
    set_valid_env(monkeypatch)

    config = load_config()

    assert isinstance(config, Config)
    assert config.google_client_id == "test-google-client-id"
    assert config.gemini_api_key == "test-gemini-api-key"
    assert config.gemini_model == "gemini-3.5-flash-lite"
    assert config.dynamodb_table_name == "test-dynamodb-table"
    assert config.max_message_length == 100
    assert config.max_request_bytes == 2048
    assert config.user_daily_limit == 10
    assert config.global_hourly_limit == 50
    assert config.global_daily_limit == 200
    assert config.gemini_timeout_seconds == 30
    assert config.session_hmac_secret == "test-session-hmac-secret"


@pytest.mark.parametrize("missing_name", list(ALL_REQUIRED))
def test_load_config_rejects_missing_required_settings(monkeypatch, missing_name):
    set_valid_env(monkeypatch)
    monkeypatch.delenv(missing_name, raising=False)

    with pytest.raises(ConfigurationError, match=missing_name):
        load_config()


@pytest.mark.parametrize("empty_name", list(ALL_REQUIRED))
def test_load_config_rejects_blank_required_settings(monkeypatch, empty_name):
    set_valid_env(monkeypatch)
    monkeypatch.setenv(empty_name, "   ")

    with pytest.raises(ConfigurationError, match=empty_name):
        load_config()


@pytest.mark.parametrize("name", list(REQUIRED_INTS))
@pytest.mark.parametrize("invalid_value", ["abc", "1.5", "0", "-1"])
def test_load_config_rejects_invalid_numeric_values(monkeypatch, name, invalid_value):
    set_valid_env(monkeypatch)
    monkeypatch.setenv(name, invalid_value)

    with pytest.raises(ConfigurationError, match=name):
        load_config()


def test_importing_config_does_not_require_environment(monkeypatch):
    clear_config_env(monkeypatch)

    import src.config as config_module

    assert hasattr(config_module, "load_config")

    with pytest.raises(ConfigurationError):
        load_config()


def test_environment_isolation_between_loads(monkeypatch):
    set_valid_env(monkeypatch)
    first = load_config()

    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    with pytest.raises(ConfigurationError, match="GEMINI_MODEL"):
        load_config()

    monkeypatch.setenv("GEMINI_MODEL", "another-gemini-model")
    monkeypatch.setenv("USER_DAILY_LIMIT", "99")

    second = load_config()

    assert first.gemini_model == "gemini-3.5-flash-lite"
    assert first.user_daily_limit == 10
    assert second.gemini_model == "another-gemini-model"
    assert second.user_daily_limit == 99
    assert first is not second