from types import SimpleNamespace

import pytest

from src.chat.gemini_client import (
    GeminiResponse,
    GeminiServiceError,
    send_message,
)


TEST_INSTRUCTIONS = "You are a helpful portfolio assistant."


class FakeInteractions:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)

        if self.error:
            raise self.error

        return self.response


class FakeGeminiClient:
    def __init__(self, response=None, error=None):
        self.interactions = FakeInteractions(response, error)


def make_config():
    return SimpleNamespace(
        gemini_api_key="test-api-key",
        gemini_model="gemini-3.5-flash-lite",
        gemini_timeout_seconds=30,
    )


def make_response(text="Hello!", interaction_id="interaction-123"):
    return SimpleNamespace(
        output_text=text,
        id=interaction_id,
    )


def test_first_message():
    client = FakeGeminiClient(response=make_response())

    result = send_message(
        "Hello",
        make_config(),
        system_instruction=TEST_INSTRUCTIONS,
        client=client,
    )

    assert result == GeminiResponse(
        text="Hello!",
        interaction_id="interaction-123",
    )

    assert client.interactions.calls == [
        {
            "model": "gemini-3.5-flash-lite",
            "input": "Hello",
            "system_instruction": TEST_INSTRUCTIONS,
        }
    ]


def test_followup_message():
    client = FakeGeminiClient(response=make_response())

    send_message(
        "Tell me more",
        make_config(),
        system_instruction=TEST_INSTRUCTIONS,
        previous_interaction_id="previous-123",
        client=client,
    )

    request = client.interactions.calls[0]

    assert request["previous_interaction_id"] == "previous-123"
    assert request["system_instruction"] == TEST_INSTRUCTIONS


def test_response_text_is_trimmed():
    client = FakeGeminiClient(
        response=make_response(text="  Hello!  ")
    )

    result = send_message(
        "Hello",
        make_config(),
        system_instruction=TEST_INSTRUCTIONS,
        client=client,
    )

    assert result.text == "Hello!"


@pytest.mark.parametrize(
    "text, interaction_id",
    [
        (None, "interaction-123"),
        ("", "interaction-123"),
        ("   ", "interaction-123"),
        ("Hello!", None),
        ("Hello!", ""),
    ],
)
def test_invalid_responses_are_rejected(text, interaction_id):
    client = FakeGeminiClient(
        response=make_response(text, interaction_id)
    )

    with pytest.raises(GeminiServiceError):
        send_message(
            "Hello",
            make_config(),
            system_instruction=TEST_INSTRUCTIONS,
            client=client,
        )


def test_api_failure_is_handled():
    client = FakeGeminiClient(
        error=RuntimeError("API unavailable")
    )

    with pytest.raises(
        GeminiServiceError,
        match="temporarily unavailable",
    ):
        send_message(
            "Hello",
            make_config(),
            system_instruction=TEST_INSTRUCTIONS,
            client=client,
        )