from dataclasses import dataclass
import json

from .embeddings import Embedder
from .vector_store import SearchHit, VectorStore


@dataclass(frozen=True)
class Context:
    text: str
    sources: list[SearchHit]


def retrieve(question: str, embedder: Embedder, store: VectorStore,
             top_k: int = 4, score_threshold: float = 0.3) -> list[SearchHit]:
    return store.search(embedder.embed_query(question), embedder.signature, top_k, score_threshold)


def build_context(hits: list[SearchHit], max_chars: int = 6000) -> Context:
    """Inclui trechos completos em ordem de relevância; nunca cita trecho omitido."""
    if max_chars <= 0:
        raise ValueError("max_chars deve ser positivo")
    blocks: list[str] = []
    sources: list[SearchHit] = []
    used = 0
    for hit in hits:
        chunk = hit.chunk
        block = (f"[{len(sources) + 1}] PDF: {json.dumps(chunk.source, ensure_ascii=False)} | "
                 f"página: {chunk.page_number} | chunk: {chunk.chunk_index}\n{chunk.text}")
        cost = len(block) + (2 if blocks else 0)
        if used + cost > max_chars:
            continue
        blocks.append(block)
        sources.append(hit)
        used += cost
    return Context("\n\n".join(blocks), sources)
