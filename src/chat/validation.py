
from dataclasses import dataclass
from uuid import UUID


class ChatValidationError(ValueError):
    """Raised when a chat request contains invalid input."""


@dataclass(frozen=True)
class ChatRequest:
    message: str
    conversation_id: str


def validate_chat_request(
    payload: object,
    max_message_length: int,
) -> ChatRequest:
    if not isinstance(payload, dict):
        raise ChatValidationError("Request body must be a JSON object")

    if set(payload) != {"message", "conversation_id"}:
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

    return ChatRequest(
        message=message,
        conversation_id=conversation_id,
    )
