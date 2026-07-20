from pathlib import Path

import pytest

from app.services.document_parser import DocumentParseError, parse_document


def test_parse_markdown_with_document_locator(tmp_path: Path):
    path = tmp_path / "sample.md"
    path.write_text("# Security policy\r\n\r\nUse MFA", encoding="utf-8")
    sections = parse_document(path)
    assert sections == [sections[0]]
    assert sections[0].locator == "document"
    assert "Security policy" in sections[0].text


def test_parse_invalid_utf8_is_redacted(tmp_path: Path):
    path = tmp_path / "bad.md"
    path.write_bytes(b"\xff")
    with pytest.raises(DocumentParseError, match="valid UTF-8"):
        parse_document(path)
