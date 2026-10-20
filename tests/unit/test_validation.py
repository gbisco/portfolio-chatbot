import pytest

from src.chat.validation import (
    ChatRequest,
    ChatValidationError,
    validate_chat_request,
)


VALID_ID = "550e8400-e29b-41d4-a716-446655440000"
MAX_LENGTH = 100
MAX_CONVERSATION_TOKEN_LENGTH = 4096


def make_payload(**overrides):
    payload = {
        "message": "Tell me about Prompble",
        "conversation_id": VALID_ID,
    }
    payload.update(overrides)
    return payload


def validate(payload, max_message_length=MAX_LENGTH):
    return validate_chat_request(
        payload,
        max_message_length,
        MAX_CONVERSATION_TOKEN_LENGTH,
    )


def test_valid_chat_request():
    result = validate(make_payload())

    assert isinstance(result, ChatRequest)
    assert result.message == "Tell me about Prompble"
    assert result.conversation_id == VALID_ID
    assert result.conversation_token is None


def test_message_whitespace_is_trimmed():
    result = validate(make_payload(message="  Hello!  "))

    assert result.message == "Hello!"


def test_message_at_maximum_length_is_accepted():
    result = validate(make_payload(message="a" * MAX_LENGTH))

    assert len(result.message) == MAX_LENGTH


@pytest.mark.parametrize("message", ["", "   ", None, 123, [], {}])
def test_invalid_messages_are_rejected(message):
    with pytest.raises(ChatValidationError):
        validate(make_payload(message=message))


def test_message_exceeding_limit_is_rejected():
    with pytest.raises(
        ChatValidationError,
        match="maximum length",
    ):
        validate(make_payload(message="a" * (MAX_LENGTH + 1)))


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
        validate(make_payload(conversation_id=conversation_id))


@pytest.mark.parametrize("payload", [None, [], "hello", 123])
def test_non_object_payloads_are_rejected(payload):
    with pytest.raises(ChatValidationError):
        validate(payload)


def test_missing_fields_are_rejected():
    with pytest.raises(ChatValidationError):
        validate({"message": "Hello"})

    with pytest.raises(ChatValidationError):
        validate({"conversation_id": VALID_ID})


def test_unexpected_fields_are_rejected():
    with pytest.raises(ChatValidationError):
        validate(make_payload(user_id="frontend-supplied-user"))


def test_validated_request_is_immutable():
    result = validate(make_payload())

    with pytest.raises(AttributeError):
        result.message = "modified"


def test_valid_followup_request():
    result = validate(make_payload(conversation_token="signed-conversation-token"))

    assert result.message == "Tell me about Prompble"
    assert result.conversation_id == VALID_ID
    assert result.conversation_token == "signed-conversation-token"


@pytest.mark.parametrize(
    "conversation_token",
    [
        "",
        123,
        [],
        {},
        True,
    ],
)
def test_invalid_conversation_tokens_are_rejected(conversation_token):
    with pytest.raises(
        ChatValidationError,
        match="Invalid conversation token",
    ):
        validate(make_payload(conversation_token=conversation_token))


def test_oversized_conversation_token_is_rejected():
    with pytest.raises(
        ChatValidationError,
        match="Invalid conversation token",
    ):
        validate(
            make_payload(
                conversation_token="a" * (MAX_CONVERSATION_TOKEN_LENGTH + 1)
            )
        )


def test_conversation_token_at_maximum_length_is_accepted():
    result = validate(
        make_payload(conversation_token="a" * MAX_CONVERSATION_TOKEN_LENGTH)
    )

    assert len(result.conversation_token) == MAX_CONVERSATION_TOKEN_LENGTH


def test_explicit_null_conversation_token_is_accepted():
    result = validate(make_payload(conversation_token=None))

    assert result.conversation_token is None
