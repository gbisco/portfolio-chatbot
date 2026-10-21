import json
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors

from src.chat.gemini_client import (
    GET_PORTFOLIO_DOCUMENT_TOOL,
    MAX_DOCUMENT_READS,
    MAX_GEMINI_INTERACTIONS,
    GeminiConversationExpired,
    GeminiResponse,
    GeminiServiceError,
    send_message,
)


TEST_INSTRUCTIONS = "You are a helpful portfolio assistant."


class FakeInteractions:
    def __init__(self, response=None, error=None, responses=None):
        self.response = response
        self.error = error
        self.responses = list(responses) if responses is not None else None
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)

        if self.responses is not None:
            if not self.responses:
                raise AssertionError("unexpected Gemini interaction")

            item = self.responses.pop(0)

            if isinstance(item, BaseException):
                raise item

            return item

        if self.error:
            raise self.error

        return self.response


class FakeGeminiClient:
    def __init__(self, response=None, error=None, responses=None):
        self.interactions = FakeInteractions(response, error, responses)


def make_config():
    return SimpleNamespace(
        gemini_api_key="test-api-key",
        gemini_model="gemini-3.5-flash-lite",
        gemini_timeout_seconds=30,
    )


def make_function_call(
    document_id="prompble",
    call_id="call-1",
    name="get_portfolio_document",
    arguments=None,
):
    if arguments is None:
        arguments = {"document_id": document_id}

    return SimpleNamespace(
        type="function_call",
        name=name,
        id=call_id,
        arguments=arguments,
    )


def make_response(text="Hello!", interaction_id="interaction-123", steps=None):
    return SimpleNamespace(
        output_text=text,
        id=interaction_id,
        steps=steps or [],
    )


def expected_create_kwargs(input, previous_interaction_id=None):
    request = {
        "model": "gemini-3.5-flash-lite",
        "input": input,
        "system_instruction": TEST_INSTRUCTIONS,
        "tools": [GET_PORTFOLIO_DOCUMENT_TOOL],
    }

    if previous_interaction_id is not None:
        request["previous_interaction_id"] = previous_interaction_id

    return request


def send(
    client,
    message="Hello",
    previous_interaction_id=None,
    document_loader=None,
):
    return send_message(
        message,
        make_config(),
        system_instruction=TEST_INSTRUCTIONS,
        previous_interaction_id=previous_interaction_id,
        document_loader=document_loader,
        client=client,
    )


def parse_function_result(payload):
    assert payload["type"] == "function_result"
    assert payload["result"][0]["type"] == "text"
    return json.loads(payload["result"][0]["text"])


def test_first_message():
    client = FakeGeminiClient(response=make_response())

    result = send(client)

    assert result == GeminiResponse(
        text="Hello!",
        interaction_id="interaction-123",
    )

    assert client.interactions.calls == [expected_create_kwargs("Hello")]


def test_followup_message():
    client = FakeGeminiClient(response=make_response())

    send(
        client,
        message="Tell me more",
        previous_interaction_id="previous-123",
    )

    assert client.interactions.calls == [
        expected_create_kwargs("Tell me more", "previous-123")
    ]


def test_response_text_is_trimmed():
    client = FakeGeminiClient(
        response=make_response(text="  Hello!  ")
    )

    result = send(client)

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
        send(client)


def make_client_error(status_code, error_code, message="error"):
    return errors.ClientError(
        status_code,
        {
            "error": {
                "code": error_code,
                "message": message,
            }
        },
    )


def test_server_error_is_handled():
    client = FakeGeminiClient(
        error=errors.ServerError(503, {"error": {"code": "service_unavailable"}})
    )

    with pytest.raises(
        GeminiServiceError,
        match="temporarily unavailable",
    ):
        send(client)


def test_transport_error_is_handled():
    client = FakeGeminiClient(
        error=httpx.ConnectError("connection failed")
    )

    with pytest.raises(
        GeminiServiceError,
        match="temporarily unavailable",
    ):
        send(client)


def test_missing_previous_interaction_is_expired():
    client = FakeGeminiClient(
        error=make_client_error(
            404,
            "not_found",
            "Failed to get completed interaction: Result not found.",
        )
    )

    with pytest.raises(GeminiConversationExpired):
        send(
            client,
            message="Tell me more",
            previous_interaction_id="expired-interaction",
        )


def test_not_found_without_previous_interaction_is_service_error():
    client = FakeGeminiClient(
        error=make_client_error(404, "not_found")
    )

    with pytest.raises(GeminiServiceError):
        send(client)


def test_model_not_found_is_not_conversation_expired():
    client = FakeGeminiClient(
        error=make_client_error(404, "model_not_found")
    )

    with pytest.raises(GeminiServiceError):
        send(
            client,
            message="Tell me more",
            previous_interaction_id="previous-123",
        )


def test_programming_errors_are_not_swallowed():
    client = FakeGeminiClient(error=TypeError("unexpected argument"))

    with pytest.raises(TypeError):
        send(client)


def test_one_retrieval_then_final_response():
    retrieved = []

    def loader(document_id):
        retrieved.append(document_id)
        return {
            "found": True,
            "document_id": document_id,
            "content": "Prompble is a tutoring platform.",
        }

    client = FakeGeminiClient(
        responses=[
            make_response(
                text="",
                interaction_id="interaction-tool",
                steps=[make_function_call("prompble", "call-1")],
            ),
            make_response(
                text="Prompble is a tutoring platform.",
                interaction_id="interaction-final",
            ),
        ]
    )

    result = send(client, document_loader=loader)

    assert result == GeminiResponse(
        text="Prompble is a tutoring platform.",
        interaction_id="interaction-final",
    )
    assert retrieved == ["prompble"]

    first, second = client.interactions.calls
    assert first == expected_create_kwargs("Hello")
    assert second["previous_interaction_id"] == "interaction-tool"
    assert second["system_instruction"] == TEST_INSTRUCTIONS
    assert second["tools"] == [GET_PORTFOLIO_DOCUMENT_TOOL]

    payload = second["input"][0]
    assert payload["name"] == "get_portfolio_document"
    assert payload["call_id"] == "call-1"
    assert parse_function_result(payload) == {
        "found": True,
        "document_id": "prompble",
        "content": "Prompble is a tutoring platform.",
    }


def test_multiple_function_calls_in_one_interaction():
    retrieved = []

    def loader(document_id):
        retrieved.append(document_id)
        return {
            "found": True,
            "document_id": document_id,
            "content": document_id,
        }

    client = FakeGeminiClient(
        responses=[
            make_response(
                text="",
                interaction_id="interaction-tools",
                steps=[
                    make_function_call("profile", "call-a"),
                    make_function_call("education", "call-b"),
                ],
            ),
            make_response(
                text="Gabriel studied mechanical engineering.",
                interaction_id="interaction-final",
            ),
        ]
    )

    result = send(client, document_loader=loader)

    assert result.interaction_id == "interaction-final"
    assert retrieved == ["profile", "education"]

    payloads = client.interactions.calls[1]["input"]
    assert [payload["call_id"] for payload in payloads] == ["call-a", "call-b"]
    assert parse_function_result(payloads[0])["document_id"] == "profile"
    assert parse_function_result(payloads[1])["document_id"] == "education"


def test_retrieval_limit_is_enforced_across_one_message():
    retrieved = []

    def loader(document_id):
        retrieved.append(document_id)
        return {
            "found": True,
            "document_id": document_id,
            "content": document_id,
        }

    extra_calls = [
        make_function_call(f"doc-{index}", f"call-{index}")
        for index in range(MAX_DOCUMENT_READS + 1)
    ]

    client = FakeGeminiClient(
        responses=[
            make_response(
                text="",
                interaction_id="interaction-tools",
                steps=extra_calls,
            ),
            make_response(
                text="I could not load every document.",
                interaction_id="interaction-final",
            ),
        ]
    )

    result = send(client, document_loader=loader)

    assert result.interaction_id == "interaction-final"
    assert retrieved == [f"doc-{index}" for index in range(MAX_DOCUMENT_READS)]

    payloads = client.interactions.calls[1]["input"]
    assert parse_function_result(payloads[-1]) == {
        "found": False,
        "error": "retrieval_limit_exceeded",
    }


def test_gemini_interaction_limit_is_enforced():
    def loader(document_id):
        return {
            "found": True,
            "document_id": document_id,
            "content": document_id,
        }

    tool_responses = [
        make_response(
            text="",
            interaction_id=f"interaction-{index}",
            steps=[make_function_call("profile", f"call-{index}")],
        )
        for index in range(MAX_GEMINI_INTERACTIONS)
    ]

    client = FakeGeminiClient(responses=tool_responses)

    with pytest.raises(GeminiServiceError, match="temporarily unavailable"):
        send(client, document_loader=loader)

    assert len(client.interactions.calls) == MAX_GEMINI_INTERACTIONS


def test_malformed_function_arguments_return_structured_error():
    def fail_loader(document_id):
        raise AssertionError("loader must not run for malformed arguments")

    client = FakeGeminiClient(
        responses=[
            make_response(
                text="",
                interaction_id="interaction-tool",
                steps=[
                    make_function_call(
                        call_id="call-bad",
                        arguments="not-json",
                    )
                ],
            ),
            make_response(
                text="I need a valid document ID.",
                interaction_id="interaction-final",
            ),
        ]
    )

    result = send(client, document_loader=fail_loader)

    assert result.interaction_id == "interaction-final"
    payload = client.interactions.calls[1]["input"][0]
    assert parse_function_result(payload) == {
        "found": False,
        "error": "invalid_arguments",
    }


def test_unknown_document_id_is_returned_without_filesystem_access():
    def loader(document_id):
        return {
            "found": False,
            "document_id": document_id,
            "error": "unknown_document",
        }

    client = FakeGeminiClient(
        responses=[
            make_response(
                text="",
                interaction_id="interaction-tool",
                steps=[make_function_call("../instructions.md", "call-1")],
            ),
            make_response(
                text="That document is not available.",
                interaction_id="interaction-final",
            ),
        ]
    )

    send(client, document_loader=loader)

    payload = client.interactions.calls[1]["input"][0]
    assert parse_function_result(payload) == {
        "found": False,
        "document_id": "../instructions.md",
        "error": "unknown_document",
    }


def test_unsupported_tool_returns_structured_error():
    def fail_loader(document_id):
        raise AssertionError("loader must not run for unsupported tools")

    client = FakeGeminiClient(
        responses=[
            make_response(
                text="",
                interaction_id="interaction-tool",
                steps=[
                    make_function_call(
                        call_id="call-other",
                        name="delete_file",
                        arguments={"path": "instructions.md"},
                    )
                ],
            ),
            make_response(
                text="I cannot use that tool.",
                interaction_id="interaction-final",
            ),
        ]
    )

    send(client, document_loader=fail_loader)

    payload = client.interactions.calls[1]["input"][0]
    assert payload["name"] == "delete_file"
    assert parse_function_result(payload) == {
        "found": False,
        "error": "unsupported_tool",
    }


def test_continuation_uses_requesting_interaction_id():
    client = FakeGeminiClient(
        responses=[
            make_response(
                text="",
                interaction_id="tool-interaction",
                steps=[make_function_call("profile", "call-1")],
            ),
            make_response(
                text="Done.",
                interaction_id="final-interaction",
            ),
        ]
    )

    send(
        client,
        previous_interaction_id="visitor-previous",
        document_loader=lambda document_id: {
            "found": True,
            "document_id": document_id,
            "content": "ok",
        },
    )

    assert client.interactions.calls[0]["previous_interaction_id"] == "visitor-previous"
    assert client.interactions.calls[1]["previous_interaction_id"] == "tool-interaction"
