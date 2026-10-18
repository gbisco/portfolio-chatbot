import base64
import json
from types import SimpleNamespace

import pytest

from src.auth.google_auth import (
    AuthenticationError,
    AuthenticationServiceError,
)
from src.auth.session import SessionError
from src.chat.gemini_client import GeminiServiceError
from src.chat.rate_limit import RateLimitDenied, RateLimitServiceError
from src.chat.validation import ChatValidationError
from src.chat.chat_service import ChatResponse
from src.config import ConfigurationError
from src.handler import lambda_handler


CONVERSATION_ID = "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def config():
    return SimpleNamespace(
        max_request_bytes=4096,
        max_message_length=100,
    )


@pytest.fixture(autouse=True)
def mock_config(monkeypatch, config):
    monkeypatch.setattr(
        "src.handler.load_config",
        lambda: config,
    )


@pytest.fixture
def mock_chat(monkeypatch):
    calls = []

    def fake_process_chat(token, payload, config):
        calls.append((token, payload, config))

        return ChatResponse(
            message="Prompble is an AI tutoring platform.",
            conversation_id=CONVERSATION_ID,
            conversation_token="signed-token-123",
        )

    monkeypatch.setattr(
        "src.handler.process_chat",
        fake_process_chat,
    )

    return calls


def make_event(
    method="POST",
    body=None,
    headers=None,
    is_base64=False,
):
    if body is None:
        body = json.dumps(
            {
                "message": "Tell me about Prompble",
                "conversation_id": CONVERSATION_ID,
            }
        )

    if headers is None:
        headers = {
            "authorization": "Bearer google-id-token",
            "content-type": "application/json",
        }

    return {
        "version": "2.0",
        "requestContext": {
            "http": {
                "method": method,
            }
        },
        "headers": headers,
        "body": body,
        "isBase64Encoded": is_base64,
    }


def parse_response(response):
    return response["statusCode"], json.loads(response["body"])


def test_successful_chat_request(mock_chat, config):
    response = lambda_handler(make_event(), None)
    status, body = parse_response(response)

    assert status == 200
    assert body == {
        "message": "Prompble is an AI tutoring platform.",
        "conversation_id": CONVERSATION_ID,
        "conversation_token": "signed-token-123",
    }

    assert len(mock_chat) == 1
    assert mock_chat[0][0] == "google-id-token"
    assert mock_chat[0][1]["message"] == "Tell me about Prompble"
    assert mock_chat[0][2] is config


def test_authorization_header_is_case_insensitive(mock_chat):
    event = make_event(
        headers={"Authorization": "Bearer google-id-token"}
    )

    response = lambda_handler(event, None)

    assert response["statusCode"] == 200
    assert len(mock_chat) == 1


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "",
        "Basic abc123",
        "Bearer",
        "Bearer ",
    ],
)
def test_invalid_authorization_is_rejected(
    authorization, mock_chat
):
    headers = {}

    if authorization is not None:
        headers["authorization"] = authorization

    response = lambda_handler(
        make_event(headers=headers),
        None,
    )

    status, body = parse_response(response)

    assert status == 401
    assert body["error"] == "unauthorized"
    assert mock_chat == []


def test_unsupported_method_is_rejected(mock_chat):
    response = lambda_handler(
        make_event(method="GET"),
        None,
    )

    status, body = parse_response(response)

    assert status == 405
    assert body["error"] == "method_not_allowed"
    assert mock_chat == []


def test_invalid_json_is_rejected(mock_chat):
    response = lambda_handler(
        make_event(body="{invalid-json"),
        None,
    )

    status, body = parse_response(response)

    assert status == 400
    assert body["error"] == "invalid_request"
    assert mock_chat == []


def test_non_string_body_is_rejected(mock_chat):
    event = make_event()
    event["body"] = {"message": "Hello"}

    response = lambda_handler(event, None)

    assert response["statusCode"] == 400
    assert mock_chat == []


def test_oversized_body_is_rejected(mock_chat):
    response = lambda_handler(
        make_event(body="a" * 4097),
        None,
    )

    status, body = parse_response(response)

    assert status == 400
    assert body["error"] == "invalid_request"
    assert mock_chat == []


def test_valid_base64_body_is_accepted(mock_chat):
    payload = json.dumps(
        {
            "message": "Hello",
            "conversation_id": CONVERSATION_ID,
        }
    )

    encoded = base64.b64encode(
        payload.encode("utf-8")
    ).decode("ascii")

    response = lambda_handler(
        make_event(body=encoded, is_base64=True),
        None,
    )

    assert response["statusCode"] == 200
    assert len(mock_chat) == 1
    assert mock_chat[0][1]["message"] == "Hello"


def test_invalid_base64_body_is_rejected(mock_chat):
    response = lambda_handler(
        make_event(body="not-valid-base64!", is_base64=True),
        None,
    )

    assert response["statusCode"] == 400
    assert mock_chat == []


@pytest.mark.parametrize(
    "error, expected_status, expected_code",
    [
        (AuthenticationError("invalid"), 401, "unauthorized"),
        (
            AuthenticationServiceError("unavailable"),
            503,
            "authentication_unavailable",
        ),
        (
            ChatValidationError("invalid"),
            400,
            "invalid_request",
        ),
        (
            SessionError("invalid"),
            403,
            "invalid_conversation",
        ),
        (
            SessionError("Conversation session expired"),
            401,
            "conversation_expired",
        ),
        (
            RateLimitServiceError("unavailable"),
            503,
            "usage_service_unavailable",
        ),
        (
            GeminiServiceError("unavailable"),
            502,
            "ai_service_unavailable",
        ),
    ],
)
def test_chat_service_errors(
    monkeypatch,
    error,
    expected_status,
    expected_code,
):
    def reject_chat(*args):
        raise error

    monkeypatch.setattr(
        "src.handler.process_chat",
        reject_chat,
    )

    response = lambda_handler(make_event(), None)
    status, body = parse_response(response)

    assert status == expected_status
    assert body["error"] == expected_code


@pytest.mark.parametrize(
    "reason",
    [
        "account_blocked",
        "user_daily_limit",
        "global_hourly_limit",
        "global_daily_limit",
    ],
)
def test_rate_limit_denials(monkeypatch, reason):
    def reject_chat(*args):
        raise RateLimitDenied(reason)

    monkeypatch.setattr(
        "src.handler.process_chat",
        reject_chat,
    )

    response = lambda_handler(make_event(), None)
    status, body = parse_response(response)

    assert status == 429
    assert body["error"] == reason
    assert body["message"]


def test_response_is_json(mock_chat):
    response = lambda_handler(make_event(), None)

    assert response["headers"]["Content-Type"] == "application/json"


def test_oversized_base64_body_is_rejected(mock_chat):
    response = lambda_handler(
        make_event(
            body="A" * 10000,
            is_base64=True,
        ),
        None,
    )

    status, body = parse_response(response)

    assert status == 400
    assert body["error"] == "invalid_request"
    assert mock_chat == []