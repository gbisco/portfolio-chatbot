from pathlib import Path

from src.chat.knowledge import DOCUMENT_FILES, KNOWLEDGE_DIR


ROOT = Path(__file__).resolve().parents[2]


def test_production_dockerfile_uses_lambda_python_base_image():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM public.ecr.aws/lambda/python:3.12" in dockerfile


def test_production_dockerfile_uses_lambda_handler_entry_point():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert 'CMD ["src.handler.lambda_handler"]' in dockerfile


def test_production_dockerfile_copies_src_including_knowledge():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY src/" in dockerfile
    assert KNOWLEDGE_DIR.is_relative_to(ROOT / "src")


def test_required_knowledge_documents_exist():
    expected = [
        "instructions.md",
        "index.md",
        *DOCUMENT_FILES.values(),
    ]

    missing = [
        relative
        for relative in expected
        if not (KNOWLEDGE_DIR / relative).is_file()
    ]

    assert missing == []
    assert len(DOCUMENT_FILES) == 9
