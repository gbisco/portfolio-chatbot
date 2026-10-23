"""Manually test local Gemini prompt and knowledge changes.

This script sends real Gemini Interactions API requests and may incur charges.
It does not run under pytest or CI, does not call Lambda, and does not use
Google sign-in or DynamoDB.

Load GEMINI_API_KEY, GEMINI_MODEL, and GEMINI_TIMEOUT_SECONDS from the
environment or a local .env file. Never print those values.

Usage, from the portfolio-chatbot directory:

    python scripts/test_prompt.py "Tell me about Gabriel"
    python scripts/test_prompt.py "Tell me about Gabriel" "What has he been building?"
    python scripts/test_prompt.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.chat import knowledge
from src.chat.gemini_client import GeminiConversationExpired, GeminiServiceError, send_message


class RecordingDocumentLoader:
    def __init__(self, loader):
        self._loader = loader
        self.requested_ids = []

    def __call__(self, document_id):
        self.requested_ids.append(document_id)
        return self._loader(document_id)


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()

        if not key or key in os.environ:
            continue

        os.environ[key] = value.strip().strip("'").strip('"')


def _gemini_config():
    _load_dotenv(ROOT / ".env")

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(
            "GEMINI_API_KEY is required. Set it in the environment or a local .env file."
        )

    timeout_raw = os.environ.get("GEMINI_TIMEOUT_SECONDS", "30").strip()

    try:
        timeout_seconds = int(timeout_raw)
    except ValueError as exc:
        raise SystemExit(
            "GEMINI_TIMEOUT_SECONDS must be a positive integer."
        ) from exc

    if timeout_seconds <= 0:
        raise SystemExit("GEMINI_TIMEOUT_SECONDS must be a positive integer.")

    return SimpleNamespace(
        gemini_api_key=api_key,
        gemini_model=os.environ.get("GEMINI_MODEL", "").strip()
        or "gemini-3.5-flash-lite",
        gemini_timeout_seconds=timeout_seconds,
    )


def _system_instruction() -> str:
    knowledge.load_instructions.cache_clear()
    knowledge.load_index.cache_clear()
    knowledge._read_document_content.cache_clear()
    instructions = knowledge.load_system_instruction()

    if not instructions.strip():
        raise SystemExit("Local instructions.md or index.md is empty.")

    return instructions


def _word_count(text: str) -> int:
    return len(text.split())


def _print_response(text: str, model: str, requested_ids: list) -> None:
    print()
    print(text)
    print()
    print(f"words: {_word_count(text)}")
    print(f"characters: {len(text)}")
    print(f"model: {model}")

    unique_ids = list(dict.fromkeys(requested_ids))
    if unique_ids:
        print(f"documents: {', '.join(unique_ids)}")


def _ask(question: str, config, loader, previous_interaction_id=None):
    print()
    print("Sending a live Gemini request. This may incur charges.")
    print(f"question: {question}")

    return send_message(
        question,
        config,
        system_instruction=_system_instruction(),
        previous_interaction_id=previous_interaction_id,
        document_loader=loader,
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Send local portfolio instructions to Gemini. "
            "Each question calls the real API and may incur charges."
        )
    )
    parser.add_argument(
        "questions",
        nargs="*",
        help="One or more test questions. Omit for an interactive session.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    config = _gemini_config()
    loader = RecordingDocumentLoader(knowledge.get_document)
    previous_interaction_id = None

    print("Local Gemini prompt tester")
    print("Each question calls the real Gemini API and may incur charges.")
    print(f"model: {config.gemini_model}")
    print("Loaded local instructions.md and index.md.")

    questions = [question.strip() for question in args.questions if question.strip()]

    if questions:
        for question in questions:
            before = len(loader.requested_ids)
            result = _ask(question, config, loader, previous_interaction_id)
            _print_response(
                result.text,
                config.gemini_model,
                loader.requested_ids[before:],
            )
            previous_interaction_id = result.interaction_id
        return

    print("Enter a question, or a blank line / quit to exit.")

    while True:
        try:
            question = input("\nquestion> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if not question or question.lower() in {"quit", "exit"}:
            return

        before = len(loader.requested_ids)

        try:
            result = _ask(question, config, loader, previous_interaction_id)
        except (GeminiServiceError, GeminiConversationExpired) as exc:
            print(f"Gemini request failed: {exc}")
            previous_interaction_id = None
            continue

        _print_response(
            result.text,
            config.gemini_model,
            loader.requested_ids[before:],
        )
        previous_interaction_id = result.interaction_id


if __name__ == "__main__":
    try:
        main()
    except (GeminiServiceError, GeminiConversationExpired) as exc:
        raise SystemExit(f"Gemini request failed: {exc}") from exc
