from dataclasses import dataclass

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


def send_message(
    message: str,
    config: Config,
    *,
    system_instruction: str,
    previous_interaction_id: str | None = None,
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

    request = {
        "model": config.gemini_model,
        "input": message,
        "system_instruction": system_instruction,
    }

    if previous_interaction_id is not None:
        request["previous_interaction_id"] = previous_interaction_id

    try:
        interaction = client.interactions.create(**request)

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
