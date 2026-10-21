"""Manual, billable Gemini Interactions API integration check.

Run this script explicitly; it deliberately has no pytest test_* functions.
It uses real Gemini requests but does not use Google sign-in or DynamoDB.
"""

import os
from types import SimpleNamespace

from src.chat.gemini_client import send_message
from src.chat.knowledge import get_document, load_system_instruction


TEST_MARKER = "violet otter 731"
TEST_INSTRUCTION_WORD = "SUNRISE"

# Facts that appear in projects/prompble.md but not in the short index catalog.
PROMPBLE_TECHNICAL_TERMS = (
    "railway",
    "resend",
    "outbox",
    "gunicorn",
    "sqlalchemy",
    "pymupdf",
)


class RecordingDocumentLoader:
    """Wrap get_document and record requested document IDs."""

    def __init__(self, loader):
        self._loader = loader
        self.requested_ids = []

    def __call__(self, document_id):
        self.requested_ids.append(document_id)
        return self._loader(document_id)


def _live_config():
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is required; supply it at runtime.")

    return SimpleNamespace(
        gemini_api_key=api_key,
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        gemini_timeout_seconds=int(os.environ.get("GEMINI_TIMEOUT_SECONDS", "60")),
    )


def _system_instruction() -> str:
    instructions = load_system_instruction()
    if not instructions.strip():
        raise AssertionError("Portfolio instructions are empty")

    # A temporary test-only instruction makes it possible to test that the
    # system_instruction field is honored, independent of portfolio content.
    return (
        instructions
        + "\n\n# Temporary API integration-test instruction\n"
        + f"When asked for the integration check word, answer {TEST_INSTRUCTION_WORD}.\n"
    )


def _assert_prompble_technical_content(text: str) -> None:
    lowered = text.lower()
    matched = [term for term in PROMPBLE_TECHNICAL_TERMS if term in lowered]
    assert matched, (
        "Retrieval response did not include Prompble technical details "
        "from the knowledge document"
    )


def main() -> None:
    config = _live_config()
    instructions = _system_instruction()
    loader = RecordingDocumentLoader(get_document)

    print(f"Calling live Gemini model: {config.gemini_model}")
    print("Turn 1: checking system instructions and introducing a memory marker...")
    first = send_message(
        (
            "What is the integration check word? "
            f"Please also remember this marker for my next message: {TEST_MARKER}."
        ),
        config,
        system_instruction=instructions,
        document_loader=loader,
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
        document_loader=loader,
    )

    print("Turn 2 response:", second.text)
    assert second.interaction_id, "Follow-up did not return an interaction ID"
    assert TEST_MARKER.lower() in second.text.lower(), (
        "Conversation continuity check failed: marker not remembered"
    )

    print("PASS: live API, system instruction, and two-turn continuity")

    retrieval_loader = RecordingDocumentLoader(get_document)

    print("Turn 3: checking live get_portfolio_document retrieval for Prompble...")
    retrieval = send_message(
        (
            "Using the portfolio knowledge documents, describe Prompble's "
            "current Railway production service names and which library or "
            "API sends student invitation emails. Include Gunicorn and the "
            "ORM if those are documented. Do not answer from the index "
            "catalog alone."
        ),
        config,
        system_instruction=instructions,
        document_loader=retrieval_loader,
    )

    print("Turn 3 response:", retrieval.text)
    assert retrieval.interaction_id, "Retrieval turn did not return an interaction ID"
    assert "prompble" in retrieval_loader.requested_ids, (
        "Gemini did not call get_portfolio_document with document_id='prompble'"
    )
    _assert_prompble_technical_content(retrieval.text)

    print("Turn 4: checking continuity after tool execution...")
    followup = send_message(
        (
            "From the Prompble production services you just described, "
            "which Railway service handles persistent event dispatch? "
            "Reply with only that service name."
        ),
        config,
        system_instruction=instructions,
        previous_interaction_id=retrieval.interaction_id,
        document_loader=retrieval_loader,
    )

    print("Turn 4 response:", followup.text)
    assert followup.interaction_id, "Post-retrieval follow-up did not return an interaction ID"
    assert "outbox" in followup.text.lower(), (
        "Conversation continuity after tool execution failed: "
        "expected the Prompble outbox worker"
    )

    unique_documents = list(dict.fromkeys(retrieval_loader.requested_ids))
    continuity = "PASS"

    print()
    print("Retrieval summary")
    print(f"  Documents retrieved: {unique_documents}")
    print(f"  Number of retrieval calls: {len(retrieval_loader.requested_ids)}")
    print(f"  Gemini response: {retrieval.text}")
    print(f"  Conversation continuity result: {continuity}")
    print("PASS: live Prompble function-calling retrieval")


if __name__ == "__main__":
    main()
