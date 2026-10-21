from functools import lru_cache
from pathlib import Path


KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"

DOCUMENT_FILES = {
    "profile": "profile.md",
    "experience": "experience.md",
    "education": "education.md",
    "prompble": "projects/prompble.md",
    "resumate": "projects/resumate.md",
    "securebank": "projects/securebank.md",
    "shinkansen": "projects/shinkansen.md",
    "techtrack": "projects/techtrack.md",
    "nplm": "projects/nplm.md",
}


def _read_knowledge_file(relative_path: str) -> str:
    knowledge_root = KNOWLEDGE_DIR.resolve()
    path = (KNOWLEDGE_DIR / relative_path).resolve()

    if not path.is_relative_to(knowledge_root):
        raise FileNotFoundError("Knowledge file is outside the knowledge directory")

    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_instructions() -> str:
    return _read_knowledge_file("instructions.md")


@lru_cache(maxsize=1)
def load_index() -> str:
    return _read_knowledge_file("index.md")


def load_system_instruction() -> str:
    """Load cached system instructions and the document catalog."""

    return f"{load_instructions()}\n\n{load_index()}"


@lru_cache(maxsize=None)
def _read_document_content(document_id: str) -> str:
    return _read_knowledge_file(DOCUMENT_FILES[document_id])


def get_document(document_id: object) -> dict:
    """Return an allowlisted knowledge document, or a structured miss."""

    if not isinstance(document_id, str) or document_id not in DOCUMENT_FILES:
        return {
            "found": False,
            "document_id": document_id if isinstance(document_id, str) else None,
            "error": "unknown_document",
        }

    try:
        content = _read_document_content(document_id)
    except OSError:
        return {
            "found": False,
            "document_id": document_id,
            "error": "unavailable",
        }

    return {
        "found": True,
        "document_id": document_id,
        "content": content,
    }
