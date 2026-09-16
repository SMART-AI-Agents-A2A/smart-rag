from dataclasses import dataclass, replace
from threading import RLock
from types import TracebackType
from typing import Self

from .config import Settings, load_settings
from .embeddings import Embedder
from .ingest import ingest
from .retriever import build_context, retrieve
from .vector_store import VectorStore


class IndexNotReadyError(RuntimeError):
    pass


@dataclass(frozen=True)
class RetrievedChunk:
    reference: int
    source: str
    page_number: int
    chunk_index: int
    score: float
    text: str


@dataclass(frozen=True)
class RetrievalResponse:
    context: str
    chunks: list[RetrievedChunk]


class RAG:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings if settings is not None else load_settings()
        self.store = VectorStore(self.settings)
        self._lock = RLock()

    def retrieve(self, question: str, *, top_k: int | None = None, score_threshold: float | None = None) -> RetrievalResponse:
        if not question.strip():
            raise ValueError("A pergunta não pode ser vazia")
        settings = replace(
            self.settings,
            top_k=top_k if top_k is not None else self.settings.top_k,
            score_threshold=score_threshold if score_threshold is not None else self.settings.score_threshold,
        )
        with self._lock:
            if not self.store.exists():
                raise IndexNotReadyError("Índice inexistente. Execute python -m src.main ingest")
            hits = retrieve(question, Embedder(settings), self.store, settings.top_k, settings.score_threshold)
            context = build_context(hits, settings.max_context_chars)
            return RetrievalResponse(context.text, [
                RetrievedChunk(reference, hit.chunk.source, hit.chunk.page_number,
                               hit.chunk.chunk_index, hit.score, hit.chunk.text)
                for reference, hit in enumerate(context.sources, start=1)
            ])

    def ingest(self, *, rebuild: bool = False) -> int:
        with self._lock:
            return ingest(self.settings, Embedder(self.settings), self.store, rebuild=rebuild)

    def close(self) -> None:
        with self._lock:
            self.store.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: type[BaseException] | None,
                 exc_value: BaseException | None, traceback: TracebackType | None) -> None:
        self.close()
