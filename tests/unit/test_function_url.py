import base64
import json
from types import SimpleNamespace

import pytest

from src.chat.chat_service import ChatResponse
from src.handler import lambda_handler


CONVERSATION_ID = "550e8400-e29b-41d4-a716-446655440000"
FUNCTION_URL_HOST = "abcdefghijklmnopqrstuvwxyz.lambda-url.us-east-1.on.aws"


@pytest.fixture
def config():
    return SimpleNamespace(
        max_request_bytes=4096,
        max_message_length=100,
        max_conversation_token_length=4096,
    )


@pytest.fixture(autouse=True)
def mock_config(monkeypatch, config):
    monkeypatch.setattr("src.handler.load_config", lambda: config)


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

    monkeypatch.setattr("src.handler.process_chat", fake_process_chat)
    return calls


def make_function_url_event(
    *,
    method="POST",
    body=None,
    headers=None,
    is_base64=False,
    omit_authorization=False,
):
    """Build a realistic Lambda Function URL payload format 2.0 event."""

    if body is None:
        body = json.dumps(
            {
                "message": "Tell me about Prompble",
                "conversation_id": CONVERSATION_ID,
            }
        )

    event_headers = {
        "content-type": "application/json",
        "host": FUNCTION_URL_HOST,
        "user-agent": "Mozilla/5.0",
        "x-amzn-tls-version": "TLSv1.3",
        "x-forwarded-port": "443",
        "x-forwarded-proto": "https",
    }

    if not omit_authorization:
        event_headers["authorization"] = "Bearer google-id-token"

    if headers is not None:
        event_headers.update(headers)

    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": "/",
        "rawQueryString": "",
        "headers": event_headers,
        "requestContext": {
            "accountId": "anonymous",
            "apiId": "abcdefghijklmnopqrstuvwxyz",
            "domainName": FUNCTION_URL_HOST,
            "domainPrefix": "abcdefghijklmnopqrstuvwxyz",
            "http": {
                "method": method,
                "path": "/",
                "protocol": "HTTP/1.1",
                "sourceIp": "203.0.113.10",
                "userAgent": "Mozilla/5.0",
            },
            "requestId": "function-url-request-id",
            "routeKey": "$default",
            "stage": "$default",
            "time": "22/Oct/2026:17:00:00 +0000",
            "timeEpoch": 1761152400000,
        },
        "body": body,
        "isBase64Encoded": is_base64,
    }


def parse_response(response):
    return response["statusCode"], json.loads(response["body"])


def assert_json_error(response, status_code, error_code):
    status, body = parse_response(response)

    assert status == status_code
    assert response["headers"] == {"Content-Type": "application/json"}
    assert "Access-Control-Allow-Origin" not in response["headers"]
    assert body["error"] == error_code
    assert isinstance(body["message"], str) and body["message"]


def test_function_url_post_is_accepted(mock_chat, config):
    event = make_function_url_event()

    response = lambda_handler(event, None)
    status, body = parse_response(response)

    assert event["version"] == "2.0"
    assert event["requestContext"]["http"]["method"] == "POST"
    assert status == 200
    assert response["headers"] == {"Content-Type": "application/json"}
    assert "Access-Control-Allow-Origin" not in response["headers"]
    assert body == {
        "message": "Prompble is an AI tutoring platform.",
        "conversation_id": CONVERSATION_ID,
        "conversation_token": "signed-token-123",
    }
    assert mock_chat[0][0] == "google-id-token"
    assert mock_chat[0][1]["message"] == "Tell me about Prompble"
    assert mock_chat[0][2] is config


@pytest.mark.parametrize(
    "headers, omit_authorization",
    [
        ({}, True),
        ({"authorization": ""}, False),
        ({"authorization": "Basic abc123"}, False),
        ({"authorization": "Bearer"}, False),
        ({"authorization": "Bearer "}, False),
    ],
)
def test_function_url_missing_or_invalid_authorization_is_rejected(
    mock_chat,
    headers,
    omit_authorization,
):
    response = lambda_handler(
        make_function_url_event(
            headers=headers,
            omit_authorization=omit_authorization,
        ),
        None,
    )

    assert_json_error(response, 401, "unauthorized")
    assert mock_chat == []


def test_function_url_malformed_json_is_rejected(mock_chat):
    response = lambda_handler(
        make_function_url_event(body="{not-json"),
        None,
    )

    assert_json_error(response, 400, "invalid_request")
    assert mock_chat == []


def test_function_url_invalid_request_payload_is_rejected():
    response = lambda_handler(
        make_function_url_event(
            body=json.dumps({"message": "Hello without a conversation id"})
        ),
        None,
    )

    assert_json_error(response, 400, "invalid_request")


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE", "OPTIONS"])
def test_function_url_unsupported_methods_are_rejected(mock_chat, method):
    response = lambda_handler(
        make_function_url_event(method=method),
        None,
    )

    assert_json_error(response, 405, "method_not_allowed")
    assert mock_chat == []


def test_function_url_base64_body_is_accepted(mock_chat):
    payload = json.dumps(
        {
            "message": "Hello from a Function URL",
            "conversation_id": CONVERSATION_ID,
        }
    )
    encoded = base64.b64encode(payload.encode("utf-8")).decode("ascii")

    response = lambda_handler(
        make_function_url_event(body=encoded, is_base64=True),
        None,
    )
    status, body = parse_response(response)

    assert status == 200
    assert body["conversation_id"] == CONVERSATION_ID
    assert mock_chat[0][1]["message"] == "Hello from a Function URL"
