"""Manual, billable Gemini Interactions API integration check.

Run this script explicitly; it deliberately has no pytest test_* functions.
It uses real Gemini requests but does not use Google sign-in or DynamoDB.
"""

import os
from types import SimpleNamespace

from src.chat.chat_service import load_portfolio_instructions
from src.chat.gemini_client import send_message


TEST_MARKER = "violet otter 731"
TEST_INSTRUCTION_WORD = "SUNRISE"


def main() -> None:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is required; supply it at runtime.")

    # send_message() only needs these three fields, not the full Lambda config.
    config = SimpleNamespace(
        gemini_api_key=api_key,
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        gemini_timeout_seconds=int(os.environ.get("GEMINI_TIMEOUT_SECONDS", "30")),
    )

    # Read the same bundled Markdown files used by chat_service.py.
    instructions = load_portfolio_instructions()
    if not instructions.strip():
        raise AssertionError("Portfolio instructions are empty")

    # A temporary test-only instruction makes it possible to test that the
    # system_instruction field is honored, independent of portfolio content.
    instructions += (
        "\n\n# Temporary API integration-test instruction\n"
        f"When asked for the integration check word, answer {TEST_INSTRUCTION_WORD}.\n"
    )

    print(f"Calling live Gemini model: {config.gemini_model}")
    print("Turn 1: checking system instructions and introducing a memory marker...")
    first = send_message(
        (
            "What is the integration check word? "
            f"Please also remember this marker for my next message: {TEST_MARKER}."
        ),
        config,
        system_instruction=instructions,
    )

    print("Turn 1 response:", first.text)
    assert first.interaction_id, "Gemini did not return an interaction ID"
    assert TEST_INSTRUCTION_WORD.lower() in first.text.lower(), (
        "System-instruction check failed: expected integration check word"
    )

    print("Turn 2: checking continuity via previous_interaction_id...")
    second = send_message(
        "What marker did I ask you to remember in my previous message? "
        "Reply with only that marker.",
        config,
        system_instruction=instructions,
        previous_interaction_id=first.interaction_id,
    )

    print("Turn 2 response:", second.text)
    assert second.interaction_id, "Follow-up did not return an interaction ID"
    assert TEST_MARKER.lower() in second.text.lower(), (
        "Conversation continuity check failed: marker not remembered"
    )

    print("PASS: live API, system instruction, and two-turn continuity")


if __name__ == "__main__":
    main()