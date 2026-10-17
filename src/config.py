import os
from dataclasses import dataclass


class ConfigurationError(ValueError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    google_client_id: str
    gcp_project_id: str
    cx_agent_id: str
    cx_location: str
    dynamodb_table_name: str
    max_message_length: int
    max_request_bytes: int
    user_daily_limit: int
    global_hourly_limit: int
    global_daily_limit: int
    cx_timeout_seconds: int
    session_hmac_secret: str


_REQUIRED_STRINGS = (
    "GOOGLE_CLIENT_ID",
    "GCP_PROJECT_ID",
    "CX_AGENT_ID",
    "CX_LOCATION",
    "DYNAMODB_TABLE_NAME",
    "SESSION_HMAC_SECRET",
)

_REQUIRED_POSITIVE_INTS = (
    "MAX_MESSAGE_LENGTH",
    "MAX_REQUEST_BYTES",
    "USER_DAILY_LIMIT",
    "GLOBAL_HOURLY_LIMIT",
    "GLOBAL_DAILY_LIMIT",
    "CX_TIMEOUT_SECONDS",
)


def _require_str(name: str) -> str:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        raise ConfigurationError(f"Missing required environment variable: {name}")
    return raw.strip()


def _require_positive_int(name: str) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        raise ConfigurationError(f"Missing required environment variable: {name}")

    stripped = raw.strip()
    try:
        value = int(stripped)
    except ValueError as exc:
        raise ConfigurationError(
            f"Invalid integer for environment variable {name}: {stripped!r}"
        ) from exc

    if value <= 0:
        raise ConfigurationError(
            f"Environment variable {name} must be a positive integer, got {value}"
        )
    return value


def load_config() -> Config:
    strings = {name: _require_str(name) for name in _REQUIRED_STRINGS}
    ints = {name: _require_positive_int(name) for name in _REQUIRED_POSITIVE_INTS}
    return Config(
        google_client_id=strings["GOOGLE_CLIENT_ID"],
        gcp_project_id=strings["GCP_PROJECT_ID"],
        cx_agent_id=strings["CX_AGENT_ID"],
        cx_location=strings["CX_LOCATION"],
        dynamodb_table_name=strings["DYNAMODB_TABLE_NAME"],
        max_message_length=ints["MAX_MESSAGE_LENGTH"],
        max_request_bytes=ints["MAX_REQUEST_BYTES"],
        user_daily_limit=ints["USER_DAILY_LIMIT"],
        global_hourly_limit=ints["GLOBAL_HOURLY_LIMIT"],
        global_daily_limit=ints["GLOBAL_DAILY_LIMIT"],
        cx_timeout_seconds=ints["CX_TIMEOUT_SECONDS"],
        session_hmac_secret=strings["SESSION_HMAC_SECRET"],
    )
