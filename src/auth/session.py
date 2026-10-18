import base64
import binascii
import hashlib
import hmac
import json
import time

from src.auth.google_auth import AuthenticatedUser


TOKEN_LIFETIME_SECONDS = 24 * 60 * 60
MAX_TOKEN_LENGTH = 4096


class SessionError(ValueError):
    """Raised when a conversation token is invalid or unauthorized."""


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.b64decode(
        value + "=" * (-len(value) % 4),
        altchars=b"-_",
        validate=True,
    )


def _user_binding(user_id: str, secret: str) -> str:
    """Create a private, deterministic identifier for the Google user."""
    return hmac.new(
        secret.encode("utf-8"),
        user_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def sign_interaction(
    user: AuthenticatedUser,
    conversation_id: str,
    interaction_id: str,
    secret: str,
) -> str:
    """Create a signed, expiring token for a Gemini interaction."""

    if (
        not isinstance(user, AuthenticatedUser)
        or not isinstance(user.user_id, str)
        or not user.user_id
        or not isinstance(conversation_id, str)
        or not conversation_id
        or not isinstance(interaction_id, str)
        or not interaction_id
        or not isinstance(secret, str)
        or not secret
    ):
        raise ValueError("Missing required session information")

    payload = {
        "user": _user_binding(user.user_id, secret),
        "conversation_id": conversation_id,
        "interaction_id": interaction_id,
        "expires_at": int(time.time()) + TOKEN_LIFETIME_SECONDS,
    }

    encoded = _encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )

    signature = hmac.new(
        secret.encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).digest()

    return f"{encoded}.{_encode(signature)}"


def verify_interaction(
    token: str,
    user: AuthenticatedUser,
    conversation_id: str,
    secret: str,
) -> str:
    """Verify conversation ownership and expiration."""

    if (
        not isinstance(token, str)
        or not token
        or len(token) > MAX_TOKEN_LENGTH
        or not isinstance(user, AuthenticatedUser)
        or not isinstance(user.user_id, str)
        or not user.user_id
        or not isinstance(conversation_id, str)
        or not conversation_id
        or not isinstance(secret, str)
        or not secret
    ):
        raise SessionError("Invalid conversation token")

    try:
        encoded, signature = token.split(".")

        expected = hmac.new(
            secret.encode("utf-8"),
            encoded.encode("ascii"),
            hashlib.sha256,
        ).digest()

        if not hmac.compare_digest(_decode(signature), expected):
            raise SessionError("Invalid conversation token")

        payload = json.loads(_decode(encoded))

        if not isinstance(payload, dict):
            raise SessionError("Invalid conversation token")

        if (
            payload.get("user") != _user_binding(user.user_id, secret)
            or payload.get("conversation_id") != conversation_id
        ):
            raise SessionError("Conversation does not belong to this user")

        expires_at = payload.get("expires_at")

        if type(expires_at) is not int or expires_at <= time.time():
            raise SessionError("Conversation session expired")

        interaction_id = payload.get("interaction_id")

        if not isinstance(interaction_id, str) or not interaction_id:
            raise SessionError("Invalid conversation token")

        return interaction_id

    except (ValueError, TypeError, UnicodeError, binascii.Error) as exc:
        if isinstance(exc, SessionError):
            raise
        raise SessionError("Invalid conversation token") from exc