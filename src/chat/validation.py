from dataclasses import dataclass
from uuid import UUID


MAX_CONVERSATION_TOKEN_LENGTH = 4096


class ChatValidationError(ValueError):
    """Raised when a chat request contains invalid input."""


@dataclass(frozen=True)
class ChatRequest:
    message: str
    conversation_id: str
    conversation_token: str | None = None


def validate_chat_request(
    payload: object,
    max_message_length: int,
) -> ChatRequest:
    """Validate the structure and content of a chat request."""

    if not isinstance(payload, dict):
        raise ChatValidationError("Request body must be a JSON object")

    required_fields = {"message", "conversation_id"}
    allowed_fields = required_fields | {"conversation_token"}

    if not required_fields.issubset(payload) or not set(payload).issubset(
        allowed_fields
    ):
        raise ChatValidationError("Invalid request fields")

    message = payload["message"]

    if not isinstance(message, str) or not message.strip():
        raise ChatValidationError("Message must be a non-empty string")

    message = message.strip()

    if len(message) > max_message_length:
        raise ChatValidationError("Message exceeds maximum length")

    conversation_id = payload["conversation_id"]

    if not isinstance(conversation_id, str):
        raise ChatValidationError("Invalid conversation ID")

    try:
        parsed_uuid = UUID(conversation_id)
    except ValueError as exc:
        raise ChatValidationError("Invalid conversation ID") from exc

    if str(parsed_uuid) != conversation_id:
        raise ChatValidationError("Invalid conversation ID")

    conversation_token = payload.get("conversation_token")

    if conversation_token is not None:
        if (
            not isinstance(conversation_token, str)
            or not conversation_token
            or len(conversation_token) > MAX_CONVERSATION_TOKEN_LENGTH
        ):
            raise ChatValidationError("Invalid conversation token")

    return ChatRequest(
        message=message,
        conversation_id=conversation_id,
        conversation_token=conversation_token,
    )