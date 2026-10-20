from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from src.auth.google_auth import AuthenticatedUser, AuthenticationError
from src.auth.session import SessionError
from src.chat.chat_service import ChatResponse, process_chat
from src.chat.gemini_client import (
    GeminiConversationExpired,
    GeminiResponse,
    GeminiServiceError,
)
from src.chat.rate_limit import RateLimitDenied


CONVERSATION_ID = "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def config():
    return SimpleNamespace(
        google_client_id="test-google-client-id",
        max_message_length=100,
        session_hmac_secret="test-session-secret",
        session_token_ttl_seconds=86400,
        max_conversation_token_length=4096,
    )


@pytest.fixture
def dependencies(monkeypatch):
    """Mock external dependencies and record their execution order."""

    from src.chat import chat_service

    calls = []

    def fake_auth(token, config):
        calls.append("auth")
        return AuthenticatedUser(user_id="google-user-123")

    def fake_validate(payload, max_message_length, max_conversation_token_length):
        calls.append("validation")

        from src.chat.validation import validate_chat_request

        return validate_chat_request(
            payload,
            max_message_length,
            max_conversation_token_length,
        )

    def fake_verify(token, user, conversation_id, secret, max_token_length):
        calls.append("session_verify")
        return "previous-interaction-123"

    def fake_rate_limit(user, config):
        calls.append("rate_limit")

    def fake_knowledge():
        calls.append("knowledge")
        return "Test portfolio instructions"

    def fake_send(message, config, **kwargs):
        calls.append("gemini")
        return GeminiResponse(
            text="Project Alpha uses React.",
            interaction_id="new-interaction-456",
        )

    def fake_sign(user, conversation_id, interaction_id, secret, token_lifetime_seconds):
        calls.append("session_sign")
        return "new-signed-token"

    monkeypatch.setattr(chat_service, "verify_google_id_token", fake_auth)
    monkeypatch.setattr(chat_service, "validate_chat_request", fake_validate)
    monkeypatch.setattr(chat_service, "verify_interaction", fake_verify)
    monkeypatch.setattr(chat_service, "enforce_rate_limits", fake_rate_limit)
    monkeypatch.setattr(chat_service, "load_portfolio_instructions", fake_knowledge)
    monkeypatch.setattr(chat_service, "send_message", fake_send)
    monkeypatch.setattr(chat_service, "sign_interaction", fake_sign)

    return SimpleNamespace(
        calls=calls,
        auth=fake_auth,
        gemini=Mock(wraps=fake_send),
    )


def make_payload(**overrides):
    payload = {
        "message": "Tell me about Project Alpha",
        "conversation_id": CONVERSATION_ID,
    }
    payload.update(overrides)
    return payload


def test_first_message(dependencies, config):
    result = process_chat("google-id-token", make_payload(), config)

    assert result == ChatResponse(
        message="Project Alpha uses React.",
        conversation_id=CONVERSATION_ID,
        conversation_token="new-signed-token",
    )

    assert dependencies.calls == [
        "validation",
        "auth",
        "rate_limit",
        "knowledge",
        "gemini",
        "session_sign",
    ]


def test_followup_message(dependencies, config):
    result = process_chat(
        "google-id-token",
        make_payload(conversation_token="existing-signed-token"),
        config,
    )

    assert result.conversation_token == "new-signed-token"

    assert dependencies.calls == [
        "validation",
        "auth",
        "session_verify",
        "rate_limit",
        "knowledge",
        "gemini",
        "session_sign",
    ]


def test_invalid_message_never_calls_gemini(dependencies, config):
    with pytest.raises(Exception):
        process_chat(
            "google-id-token",
            make_payload(message=""),
            config,
        )

    assert "gemini" not in dependencies.calls
    assert "rate_limit" not in dependencies.calls


def test_invalid_google_token_never_calls_gemini(
    dependencies, config, monkeypatch
):
    from src.chat import chat_service

    def reject_auth(token, config):
        raise AuthenticationError("Invalid identity token")

    monkeypatch.setattr(chat_service, "verify_google_id_token", reject_auth)

    with pytest.raises(AuthenticationError):
        process_chat("invalid-token", make_payload(), config)

    assert "gemini" not in dependencies.calls
    assert "rate_limit" not in dependencies.calls


def test_invalid_session_never_calls_gemini(
    dependencies, config, monkeypatch
):
    from src.chat import chat_service

    def reject_session(*args):
        raise SessionError("Invalid conversation token")

    monkeypatch.setattr(chat_service, "verify_interaction", reject_session)

    with pytest.raises(SessionError):
        process_chat(
            "google-id-token",
            make_payload(conversation_token="invalid-token"),
            config,
        )

    assert "gemini" not in dependencies.calls
    assert "rate_limit" not in dependencies.calls


def test_quota_denial_never_calls_gemini(
    dependencies, config, monkeypatch
):
    from src.chat import chat_service

    def reject_quota(user, config):
        raise RateLimitDenied("user_daily_limit")

    monkeypatch.setattr(chat_service, "enforce_rate_limits", reject_quota)

    with pytest.raises(RateLimitDenied) as exc_info:
        process_chat("google-id-token", make_payload(), config)

    assert exc_info.value.reason == "user_daily_limit"
    assert "gemini" not in dependencies.calls


def test_gemini_failure_is_propagated(
    dependencies, config, monkeypatch
):
    from src.chat import chat_service

    def reject_gemini(*args, **kwargs):
        raise GeminiServiceError("Gemini is temporarily unavailable")

    monkeypatch.setattr(chat_service, "send_message", reject_gemini)

    with pytest.raises(GeminiServiceError):
        process_chat("google-id-token", make_payload(), config)

    assert "rate_limit" in dependencies.calls
    assert "session_sign" not in dependencies.calls


def test_expired_gemini_interaction_is_propagated(
    dependencies, config, monkeypatch
):
    from src.chat import chat_service

    def reject_gemini(*args, **kwargs):
        raise GeminiConversationExpired(
            "Gemini could not retrieve the previous interaction"
        )

    monkeypatch.setattr(chat_service, "send_message", reject_gemini)

    with pytest.raises(GeminiConversationExpired):
        process_chat(
            "google-id-token",
            make_payload(conversation_token="existing-signed-token"),
            config,
        )

    assert "rate_limit" in dependencies.calls
    assert "session_sign" not in dependencies.calls