import pytest
from google.auth.exceptions import GoogleAuthError, TransportError

from src.auth.google_auth import (
    AuthenticatedUser,
    AuthenticationError,
    AuthenticationServiceError,
    verify_google_id_token,
)
from src.config import Config


def make_config(**overrides) -> Config:
    values = {
        "google_client_id": "test-google-client-id",
        "gcp_project_id": "test-gcp-project-id",
        "cx_agent_id": "test-cx-agent-id",
        "cx_location": "test-cx-location",
        "dynamodb_table_name": "test-dynamodb-table",
        "max_message_length": 100,
        "max_request_bytes": 2048,
        "user_daily_limit": 10,
        "global_hourly_limit": 50,
        "global_daily_limit": 200,
        "cx_timeout_seconds": 15,
        "session_hmac_secret": "test-session-hmac-secret",
    }
    values.update(overrides)
    return Config(**values)


def test_successful_verification_extracts_user_id():
    def fake_verify(token: str, audience: str):
        assert token == "valid-id-token"
        assert audience == "test-google-client-id"
        return {"sub": "google-user-123", "email": "ignored@example.com"}

    user = verify_google_id_token(
        "valid-id-token",
        make_config(),
        verify_token=fake_verify,
    )

    assert isinstance(user, AuthenticatedUser)
    assert user.user_id == "google-user-123"


def test_authenticated_user_is_immutable():
    user = AuthenticatedUser(user_id="google-user-123")

    with pytest.raises(AttributeError):
        user.user_id = "someone-else"


@pytest.mark.parametrize("token", [None, "", "   ", 123, [], {}])
def test_missing_token_is_rejected(token):
    def fake_verify(token: str, audience: str):
        raise AssertionError("token verification must not be called")

    with pytest.raises(AuthenticationError, match="Missing or invalid identity token"):
        verify_google_id_token(token, make_config(), verify_token=fake_verify)


def test_invalid_token_is_rejected():
    def fake_verify(token: str, audience: str):
        raise ValueError("Token is malformed")

    with pytest.raises(AuthenticationError, match="Invalid identity token"):
        verify_google_id_token("malformed-token", make_config(), verify_token=fake_verify)


def test_google_auth_error_is_rejected():
    def fake_verify(token: str, audience: str):
        raise GoogleAuthError("verification failed")

    with pytest.raises(AuthenticationError, match="Invalid identity token"):
        verify_google_id_token("bad-token", make_config(), verify_token=fake_verify)


def test_wrong_audience_is_rejected():
    def fake_verify(token: str, audience: str):
        raise ValueError("Token has wrong audience")

    with pytest.raises(AuthenticationError, match="Invalid identity token"):
        verify_google_id_token("valid-id-token", make_config(), verify_token=fake_verify)


def test_expired_token_is_rejected():
    def fake_verify(token: str, audience: str):
        raise ValueError("Token expired")

    with pytest.raises(AuthenticationError, match="Invalid identity token"):
        verify_google_id_token("expired-token", make_config(), verify_token=fake_verify)


@pytest.mark.parametrize(
    "claims",
    [
        {},
        {"email": "attacker@example.com"},
        {"sub": ""},
        {"sub": "   "},
        {"sub": 12345},
        {"sub": None},
    ],
)
def test_missing_or_invalid_sub_is_rejected(claims):
    def fake_verify(token: str, audience: str):
        return claims

    with pytest.raises(AuthenticationError, match="missing subject"):
        verify_google_id_token("valid-id-token", make_config(), verify_token=fake_verify)


def test_does_not_trust_frontend_supplied_user_id():
    def fake_verify(token: str, audience: str):
        return {"sub": "verified-google-sub"}

    user = verify_google_id_token(
        "valid-id-token",
        make_config(),
        verify_token=fake_verify,
    )

    assert user.user_id == "verified-google-sub"
    assert user.user_id != "frontend-user-id"


def test_default_verifier_uses_google_library_with_configured_audience(monkeypatch):
    from src.auth import google_auth

    captured = {}

    def fake_request(url, **kwargs):
        return None

    def fake_google_verify(token, request, audience=None):
        captured["token"] = token
        captured["audience"] = audience
        captured["request"] = request
        return {"sub": "library-user"}

    monkeypatch.setattr(
        google_auth,
        "_get_cached_google_request",
        lambda: fake_request,
    )

    monkeypatch.setattr(
        google_auth.id_token,
        "verify_oauth2_token",
        fake_google_verify,
    )

    user = verify_google_id_token("library-token", make_config())

    assert user.user_id == "library-user"
    assert captured["token"] == "library-token"
    assert captured["audience"] == "test-google-client-id"
    assert callable(captured["request"])


def test_google_request_transport_is_reused():
    from src.auth.google_auth import _get_cached_google_request

    _get_cached_google_request.cache_clear()

    try:
        first = _get_cached_google_request()
        second = _get_cached_google_request()

        assert first is second
        assert first.session is second.session
    finally:
        _get_cached_google_request.cache_clear()


def test_google_verification_transport_failure():
    def fake_verify(token: str, audience: str):
        raise TransportError("Unable to retrieve Google certificates")

    with pytest.raises(
        AuthenticationServiceError,
        match="temporarily unavailable",
    ):
        verify_google_id_token(
            "valid-id-token",
            make_config(),
            verify_token=fake_verify,
        )
