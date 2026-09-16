from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass(frozen=True)
class DocumentPage:
    source: str
    page_number: int
    text: str


def load_pdf_pages(documents_dir: str | Path) -> list[DocumentPage]:
    """Lê *.pdf diretamente na pasta, em ordem de nome; páginas começam em 1.

    Páginas vazias são ignoradas sem alterar a numeração original.
    Pasta ausente ou PDF ilegível causa erro, evitando ingestão parcial silenciosa.
    """
    directory = Path(documents_dir)
    if not directory.is_dir():
        raise NotADirectoryError(f"Pasta de documentos inválida: {directory}")

    pages: list[DocumentPage] = []
    for path in sorted(directory.glob("*.pdf")):
        if not path.is_file():
            continue
        try:
            with path.open("rb") as stream:
                reader = PdfReader(stream)
                for page_number, page in enumerate(reader.pages, start=1):
                    text = (page.extract_text() or "").strip()
                    if text:
                        pages.append(DocumentPage(path.name, page_number, text))
        except Exception as exc:
            raise RuntimeError(f"Falha ao extrair o PDF: {path}") from exc
    return pages
