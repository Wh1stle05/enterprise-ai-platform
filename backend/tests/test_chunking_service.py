import pytest

from app.services.chunking_service import chunk_sections
from app.services.document_parser import SourceSection


def test_chunking_has_stable_indices_and_overlap():
    chunks = chunk_sections(
        [SourceSection("A" * 900 + "\n\n" + "B" * 900, "page 1")],
        chunk_size=1000,
        chunk_overlap=200,
    )
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    assert all(len(chunk.content) <= 1000 and chunk.source_locator == "page 1" for chunk in chunks)
    assert chunks[0].content[-200:] in chunks[1].content


def test_chunking_validates_overlap():
    with pytest.raises(ValueError):
        chunk_sections([], chunk_size=10, chunk_overlap=10)
