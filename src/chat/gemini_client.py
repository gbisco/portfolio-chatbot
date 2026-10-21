from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

import httpx
from google import genai
from google.genai import errors, types

from src.config import Config


class GeminiServiceError(Exception):
    """Raised when Gemini cannot complete a request."""


class GeminiConversationExpired(Exception):
    """Raised when Gemini cannot retrieve a previous interaction."""


@dataclass(frozen=True)
class GeminiResponse:
    text: str
    interaction_id: str


DocumentLoader = Callable[[object], dict]

MAX_GEMINI_INTERACTIONS = 3
MAX_DOCUMENT_READS = 4

GET_PORTFOLIO_DOCUMENT_TOOL = {
    "type": "function",
    "name": "get_portfolio_document",
    "description": (
        "Retrieve one allowlisted portfolio knowledge document by document_id "
        "from the catalog. Use this for facts about Gabriel. Do not guess "
        "document IDs that are not listed in the index."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "document_id": {
                "type": "string",
                "description": "Allowlisted document ID from the knowledge index.",
            },
        },
        "required": ["document_id"],
    },
}


def _interactions_error_code(exc: errors.APIError) -> object:
    details = exc.details

    if not isinstance(details, dict):
        return None

    payload = details.get("error", details)

    if not isinstance(payload, dict):
        return None

    return payload.get("code")


def _is_missing_previous_interaction(exc: errors.ClientError) -> bool:
    """True when Gemini reports that a stored interaction cannot be retrieved."""

    return exc.code == 404 and _interactions_error_code(exc) == "not_found"


def _function_call_steps(interaction) -> list:
    steps = getattr(interaction, "steps", None) or []
    return [
        step
        for step in steps
        if getattr(step, "type", None) == "function_call"
    ]


def _tool_error(error: str, **fields) -> dict:
    return {"found": False, "error": error, **fields}


def _execute_document_tool(
    step,
    document_loader: DocumentLoader | None,
    document_reads: int,
) -> tuple[dict, int]:
    name = getattr(step, "name", None)

    if name != "get_portfolio_document":
        return _tool_error("unsupported_tool"), document_reads

    if document_reads >= MAX_DOCUMENT_READS:
        return _tool_error("retrieval_limit_exceeded"), document_reads

    arguments = getattr(step, "arguments", None)

    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return _tool_error("invalid_arguments"), document_reads

    if not isinstance(arguments, dict):
        return _tool_error("invalid_arguments"), document_reads

    if "document_id" not in arguments:
        return _tool_error("invalid_arguments"), document_reads

    document_id = arguments["document_id"]
    document_reads += 1

    if document_loader is None:
        return (
            _tool_error("unavailable", document_id=document_id if isinstance(document_id, str) else None),
            document_reads,
        )

    result = document_loader(document_id)

    if not isinstance(result, dict):
        return (
            _tool_error(
                "unavailable",
                document_id=document_id if isinstance(document_id, str) else None,
            ),
            document_reads,
        )

    return result, document_reads


def _function_result(step, result: dict) -> dict:
    return {
        "type": "function_result",
        "name": getattr(step, "name", None),
        "call_id": getattr(step, "id", None),
        "result": [
            {
                "type": "text",
                "text": json.dumps(result),
            }
        ],
    }


def _create_interaction(
    client,
    config: Config,
    *,
    input,
    system_instruction: str,
    previous_interaction_id: str | None,
):
    request = {
        "model": config.gemini_model,
        "input": input,
        "system_instruction": system_instruction,
        "tools": [GET_PORTFOLIO_DOCUMENT_TOOL],
    }

    if previous_interaction_id is not None:
        request["previous_interaction_id"] = previous_interaction_id

    try:
        return client.interactions.create(**request)

    except errors.ClientError as exc:
        if previous_interaction_id is not None and _is_missing_previous_interaction(
            exc
        ):
            raise GeminiConversationExpired(
                "Gemini could not retrieve the previous interaction"
            ) from exc

        raise GeminiServiceError(
            "Gemini is temporarily unavailable"
        ) from exc

    except (errors.APIError, httpx.RequestError, TimeoutError) as exc:
        raise GeminiServiceError(
            "Gemini is temporarily unavailable"
        ) from exc


def _final_response(interaction) -> GeminiResponse:
    text = interaction.output_text
    interaction_id = interaction.id

    if (
        not isinstance(text, str)
        or not text.strip()
        or not isinstance(interaction_id, str)
        or not interaction_id
    ):
        raise GeminiServiceError(
            "Gemini returned an invalid response"
        )

    return GeminiResponse(
        text=text.strip(),
        interaction_id=interaction_id,
    )


def send_message(
    message: str,
    config: Config,
    *,
    system_instruction: str,
    previous_interaction_id: str | None = None,
    document_loader: DocumentLoader | None = None,
    client=None,
) -> GeminiResponse:
    """Send a message using the Gemini Interactions API."""

    if client is None:
        client = genai.Client(
            api_key=config.gemini_api_key,
            http_options=types.HttpOptions(
                timeout=config.gemini_timeout_seconds * 1000,
            ),
        )

    document_reads = 0
    interaction_count = 0
    current_input = message
    current_previous_id = previous_interaction_id

    while True:
        if interaction_count >= MAX_GEMINI_INTERACTIONS:
            raise GeminiServiceError(
                "Gemini is temporarily unavailable"
            )

        interaction = _create_interaction(
            client,
            config,
            input=current_input,
            system_instruction=system_instruction,
            previous_interaction_id=current_previous_id,
        )
        interaction_count += 1

        function_calls = _function_call_steps(interaction)

        if not function_calls:
            return _final_response(interaction)

        if interaction_count >= MAX_GEMINI_INTERACTIONS:
            raise GeminiServiceError(
                "Gemini is temporarily unavailable"
            )

        results = []

        for step in function_calls:
            result, document_reads = _execute_document_tool(
                step,
                document_loader,
                document_reads,
            )
            results.append(_function_result(step, result))

        current_input = results
        current_previous_id = interaction.id
