
import pytest

from src.chat.validation import (
    ChatRequest,
    ChatValidationError,
    validate_chat_request,
)


VALID_ID = "550e8400-e29b-41d4-a716-446655440000"
MAX_LENGTH = 100


def make_payload(**overrides):
    payload = {
        "message": "Tell me about Prompble",
        "conversation_id": VALID_ID,
    }
    payload.update(overrides)
    return payload


def test_valid_chat_request():
    result = validate_chat_request(make_payload(), MAX_LENGTH)

    assert isinstance(result, ChatRequest)
    assert result.message == "Tell me about Prompble"
    assert result.conversation_id == VALID_ID


def test_message_whitespace_is_trimmed():
    result = validate_chat_request(
        make_payload(message="  Hello!  "),
        MAX_LENGTH,
    )

    assert result.message == "Hello!"


def test_message_at_maximum_length_is_accepted():
    result = validate_chat_request(
        make_payload(message="a" * MAX_LENGTH),
        MAX_LENGTH,
    )

    assert len(result.message) == MAX_LENGTH


@pytest.mark.parametrize("message", ["", "   ", None, 123, [], {}])
def test_invalid_messages_are_rejected(message):
    with pytest.raises(ChatValidationError):
        validate_chat_request(
            make_payload(message=message),
            MAX_LENGTH,
        )


def test_message_exceeding_limit_is_rejected():
    with pytest.raises(
        ChatValidationError,
        match="maximum length",
    ):
        validate_chat_request(
            make_payload(message="a" * (MAX_LENGTH + 1)),
            MAX_LENGTH,
        )


@pytest.mark.parametrize(
    "conversation_id",
    [
        "",
        "not-a-uuid",
        "12345",
        None,
        123,
        "550E8400-E29B-41D4-A716-446655440000",
    ],
)
def test_invalid_conversation_ids_are_rejected(conversation_id):
    with pytest.raises(ChatValidationError):
        validate_chat_request(
            make_payload(conversation_id=conversation_id),
            MAX_LENGTH,
        )


@pytest.mark.parametrize("payload", [None, [], "hello", 123])
def test_non_object_payloads_are_rejected(payload):
    with pytest.raises(ChatValidationError):
        validate_chat_request(payload, MAX_LENGTH)


def test_missing_fields_are_rejected():
    with pytest.raises(ChatValidationError):
        validate_chat_request({"message": "Hello"}, MAX_LENGTH)

    with pytest.raises(ChatValidationError):
        validate_chat_request({"conversation_id": VALID_ID}, MAX_LENGTH)


def test_unexpected_fields_are_rejected():
    with pytest.raises(ChatValidationError):
        validate_chat_request(
            make_payload(user_id="frontend-supplied-user"),
            MAX_LENGTH,
        )


def test_validated_request_is_immutable():
    result = validate_chat_request(make_payload(), MAX_LENGTH)

    with pytest.raises(AttributeError):
        result.message = "modified"
