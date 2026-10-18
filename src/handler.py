import base64
import binascii
import json

from src.auth.google_auth import (
    AuthenticationError,
    AuthenticationServiceError,
)
from src.auth.session import SessionError
from src.chat.chat_service import process_chat
from src.chat.gemini_client import GeminiServiceError
from src.chat.rate_limit import RateLimitDenied, RateLimitServiceError
from src.chat.validation import ChatValidationError
from src.config import ConfigurationError, load_config


def _response(status_code: int, body: dict) -> dict:
    """Build an API Gateway HTTP API response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(body),
    }


def _error(status_code: int, code: str, message: str) -> dict:
    return _response(
        status_code,
        {
            "error": code,
            "message": message,
        },
    )


def _extract_token(headers: dict) -> str:
    """Extract the Google ID token from the Authorization header."""
    authorization = next(
        (
            value
            for name, value in headers.items()
            if name.lower() == "authorization"
        ),
        None,
    )

    if not isinstance(authorization, str):
        raise AuthenticationError("Missing authorization")

    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token.strip():
        raise AuthenticationError("Invalid authorization")

    return token.strip()


def _parse_body(event: dict, max_request_bytes: int) -> object:
    """Decode and parse the HTTP request body."""

    raw_body = event.get("body")

    if not isinstance(raw_body, str):
        raise ChatValidationError("Invalid request body")

    if event.get("isBase64Encoded", False):
        # Base64 expands data by approximately 4/3.
        # Reject oversized encoded bodies before decoding.
        max_encoded_length = 4 * ((max_request_bytes + 2) // 3)

        if len(raw_body) > max_encoded_length:
            raise ChatValidationError("Request body exceeds maximum size")

        try:
            body_bytes = base64.b64decode(
                raw_body,
                validate=True,
            )
        except (ValueError, binascii.Error) as exc:
            raise ChatValidationError("Invalid request encoding") from exc

    else:
        # ASCII characters are one byte each. Reject obviously oversized
        # bodies before UTF-8 encoding.
        if len(raw_body) > max_request_bytes:
            raise ChatValidationError("Request body exceeds maximum size")

        body_bytes = raw_body.encode("utf-8")

    # Always enforce the limit against the actual decoded byte size.
    if len(body_bytes) > max_request_bytes:
        raise ChatValidationError("Request body exceeds maximum size")

    try:
        return json.loads(body_bytes)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ChatValidationError("Invalid JSON body") from exc


def lambda_handler(event: dict, context) -> dict:
    """AWS Lambda entry point for portfolio chat requests."""

    try:
        config = load_config()

        method = event.get("requestContext", {}).get("http", {}).get("method")

        if method != "POST":
            return _error(
                405,
                "method_not_allowed",
                "Only POST requests are supported.",
            )

        token = _extract_token(event.get("headers") or {})

        payload = _parse_body(
            event,
            config.max_request_bytes,
        )

        result = process_chat(
            token,
            payload,
            config,
        )

        return _response(
            200,
            {
                "message": result.message,
                "conversation_id": result.conversation_id,
                "conversation_token": result.conversation_token,
            },
        )

    except AuthenticationError:
        return _error(
            401,
            "unauthorized",
            "Please sign in with Google to use the assistant.",
        )

    except AuthenticationServiceError:
        return _error(
            503,
            "authentication_unavailable",
            "Authentication is temporarily unavailable.",
        )

    except ChatValidationError:
        return _error(
            400,
            "invalid_request",
            "The chat request is invalid.",
        )

    except SessionError as exc:
        if str(exc) == "Conversation session expired":
            return _error(
                401,
                "conversation_expired",
                "Your conversation has expired. Please start a new chat.",
            )

        return _error(
            403,
            "invalid_conversation",
            "This conversation is invalid or unavailable.",
        )

    except RateLimitDenied as exc:
        messages = {
            "account_blocked": (
                "Chat access is currently unavailable for this account."
            ),
            "user_daily_limit": (
                "You've reached your daily message limit. "
                "Please try again tomorrow."
            ),
            "global_hourly_limit": (
                "The assistant is experiencing high traffic. "
                "Please try again later."
            ),
            "global_daily_limit": (
                "The assistant has reached its capacity for today. "
                "Please try again tomorrow."
            ),
        }

        return _error(
            429,
            exc.reason,
            messages.get(exc.reason, "Chat usage limit reached."),
        )

    except RateLimitServiceError:
        return _error(
            503,
            "usage_service_unavailable",
            "The assistant is temporarily unavailable.",
        )

    except GeminiServiceError:
        return _error(
            502,
            "ai_service_unavailable",
            "The assistant couldn't complete your request. Please try again.",
        )

    except ConfigurationError:
        return _error(
            500,
            "configuration_error",
            "The assistant is temporarily unavailable.",
        )