from dataclasses import dataclass
from typing import Sequence

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.document_parser import SourceSection


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str
    source_locator: str


def chunk_sections(
    sections: Sequence[SourceSection], *, chunk_size: int, chunk_overlap: int
) -> list[TextChunk]:
    if chunk_size <= 0 or not 0 <= chunk_overlap < chunk_size:
        raise ValueError("chunk_overlap must satisfy 0 <= chunk_overlap < chunk_size")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=[""],
        length_function=len,
    )
    result: list[TextChunk] = []
    for section in sections:
        for content in splitter.split_text(section.text.replace("\n\n", " ")):
            if content.strip():
                result.append(TextChunk(len(result), content.strip(), section.locator))
    return result
