from .chunker import chunk_pages
from .config import Settings
from .embeddings import Embedder
from .pdf_loader import load_pdf_pages
from .vector_store import VectorStore


def ingest(settings: Settings, embedder: Embedder, store: VectorStore,
           rebuild: bool = False) -> int:
    if store.exists() and not rebuild:
        raise ValueError("Coleção já existe. Use ingest --rebuild para substituir o índice")
    pages = load_pdf_pages(settings.documents_dir)
    chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        raise ValueError("Nenhum texto para ingerir; o índice existente foi preservado")
    vectors = embedder.embed_documents([chunk.text for chunk in chunks])
    store.write_snapshot(chunks, vectors, embedder.signature, rebuild=rebuild)
    return len(chunks)
