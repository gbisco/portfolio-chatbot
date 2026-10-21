from pathlib import Path

import pytest

from src.chat import knowledge


MALICIOUS_IDS = (
    "../instructions.md",
    "..\\instructions.md",
    "instructions.md",
    "index.md",
    "projects/prompble.md",
    "/etc/passwd",
    "profile.md",
    "profile/../experience",
    "",
    "unknown",
)


@pytest.fixture(autouse=True)
def isolated_knowledge_cache():
    knowledge.load_instructions.cache_clear()
    knowledge.load_index.cache_clear()
    knowledge._read_document_content.cache_clear()
    yield
    knowledge.load_instructions.cache_clear()
    knowledge.load_index.cache_clear()
    knowledge._read_document_content.cache_clear()


def test_system_instruction_includes_instructions_and_index():
    system_instruction = knowledge.load_system_instruction()

    assert "You are the AI assistant" in system_instruction
    assert "profile" in system_instruction
    assert knowledge.load_instructions() in system_instruction
    assert knowledge.load_index() in system_instruction


def test_instructions_and_index_are_cached(tmp_path, monkeypatch):
    instructions = tmp_path / "instructions.md"
    index = tmp_path / "index.md"
    instructions.write_text("first instructions", encoding="utf-8")
    index.write_text("first index", encoding="utf-8")

    monkeypatch.setattr(knowledge, "KNOWLEDGE_DIR", tmp_path)

    first = knowledge.load_system_instruction()
    instructions.write_text("changed instructions", encoding="utf-8")
    index.write_text("changed index", encoding="utf-8")
    second = knowledge.load_system_instruction()

    assert first == "first instructions\n\nfirst index"
    assert second == first


def test_valid_document_retrieval():
    result = knowledge.get_document("prompble")

    assert result["found"] is True
    assert result["document_id"] == "prompble"
    assert "Prompble" in result["content"]
    assert "error" not in result


def test_document_content_is_cached(tmp_path, monkeypatch):
    (tmp_path / "profile.md").write_text("original profile", encoding="utf-8")
    monkeypatch.setattr(knowledge, "KNOWLEDGE_DIR", tmp_path)

    first = knowledge.get_document("profile")
    (tmp_path / "profile.md").write_text("changed profile", encoding="utf-8")
    second = knowledge.get_document("profile")

    assert first["content"] == "original profile"
    assert second["content"] == "original profile"


@pytest.mark.parametrize("document_id", MALICIOUS_IDS)
def test_unknown_and_malicious_document_ids_are_rejected(document_id):
    result = knowledge.get_document(document_id)

    assert result == {
        "found": False,
        "document_id": document_id,
        "error": "unknown_document",
    }


def test_non_string_document_id_is_rejected():
    result = knowledge.get_document(["profile"])

    assert result == {
        "found": False,
        "document_id": None,
        "error": "unknown_document",
    }


def test_missing_allowlisted_file_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(knowledge, "KNOWLEDGE_DIR", tmp_path)

    result = knowledge.get_document("profile")

    assert result == {
        "found": False,
        "document_id": "profile",
        "error": "unavailable",
    }


def test_get_document_does_not_read_instructions(monkeypatch):
    def fail_if_instructions(relative_path: str) -> str:
        if Path(relative_path).name == "instructions.md":
            raise AssertionError("instructions.md must not be retrieved")
        raise FileNotFoundError(relative_path)

    monkeypatch.setattr(knowledge, "_read_knowledge_file", fail_if_instructions)

    result = knowledge.get_document("instructions")

    assert result["found"] is False
    assert result["error"] == "unknown_document"
