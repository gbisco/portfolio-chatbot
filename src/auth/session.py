
import hashlib
import hmac

from src.auth.google_auth import AuthenticatedUser


def derive_cx_session_id(
    user: AuthenticatedUser,
    conversation_id: str,
    secret: str,
) -> str:
    """Derive an account-bound Dialogflow CX session identifier."""
    if not user.user_id:
        raise ValueError("Authenticated user ID is required")

    if not isinstance(conversation_id, str) or not conversation_id:
        raise ValueError("Conversation ID is required")

    if not isinstance(secret, str) or not secret:
        raise ValueError("Session secret is required")

    message = f"{user.user_id}:{conversation_id}".encode("utf-8")

    digest = hmac.new(
        secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()

    return digest[:32]
