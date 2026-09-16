from dataclasses import dataclass

from .pdf_loader import DocumentPage


@dataclass(frozen=True)
class DocumentChunk:
    source: str
    page_number: int
    chunk_index: int
    text: str


def chunk_pages(
    pages: list[DocumentPage],
    chunk_size: int = 1000,
    overlap: int = 200,
) -> list[DocumentChunk]:
    if type(chunk_size) is not int or chunk_size <= 0:
        raise ValueError("chunk_size deve ser um inteiro positivo")
    if type(overlap) is not int or not 0 <= overlap < chunk_size:
        raise ValueError("overlap deve ser um inteiro entre 0 e chunk_size - 1")

    chunks: list[DocumentChunk] = []
    step = chunk_size - overlap
    for page in pages:
        chunk_index = 0
        for start in range(0, len(page.text), step):
            text = page.text[start : start + chunk_size]
            if text.strip():
                chunks.append(
                    DocumentChunk(page.source, page.page_number, chunk_index, text)
                )
                chunk_index += 1
            if start + chunk_size >= len(page.text):
                break
    return chunks
