from dataclasses import dataclass

from src.auth.google_auth import verify_google_id_token
from src.auth.session import sign_interaction, verify_interaction
from src.chat.gemini_client import send_message
from src.chat.knowledge import get_document, load_system_instruction
from src.chat.rate_limit import enforce_rate_limits
from src.chat.validation import validate_chat_request
from src.config import Config


@dataclass(frozen=True)
class ChatResponse:
    message: str
    conversation_id: str
    conversation_token: str


def process_chat(
    token: str,
    payload: object,
    config: Config,
) -> ChatResponse:
    """Validate, authorize, and process a portfolio chat message."""

    # Validate the incoming request.
    request = validate_chat_request(
        payload,
        config.max_message_length,
        config.max_conversation_token_length,
    )

    # Verify the visitor's Google identity.
    user = verify_google_id_token(token, config)

    # Verify conversation ownership for follow-up messages.
    previous_interaction_id = None

    if request.conversation_token is not None:
        previous_interaction_id = verify_interaction(
            request.conversation_token,
            user,
            request.conversation_id,
            config.session_hmac_secret,
            config.max_conversation_token_length,
        )

    # Enforce account and global usage limits before calling Gemini.
    enforce_rate_limits(user, config)

    # Load system instructions and the document catalog.
    system_instruction = load_system_instruction()

    # Send the message to Gemini.
    result = send_message(
        request.message,
        config,
        system_instruction=system_instruction,
        previous_interaction_id=previous_interaction_id,
        document_loader=get_document,
    )

    # Bind the returned interaction to the authenticated visitor.
    conversation_token = sign_interaction(
        user,
        request.conversation_id,
        result.interaction_id,
        config.session_hmac_secret,
        config.session_token_ttl_seconds,
    )

    return ChatResponse(
        message=result.text,
        conversation_id=request.conversation_id,
        conversation_token=conversation_token,
    )
