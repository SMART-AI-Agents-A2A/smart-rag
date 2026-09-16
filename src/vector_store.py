from dataclasses import asdict, dataclass
import json
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from .chunker import DocumentChunk
from .config import Settings


@dataclass(frozen=True)
class SearchHit:
    chunk: DocumentChunk
    score: float


class VectorStore:
    def __init__(self, settings: Settings) -> None:
        self.collection = settings.collection
        self.client = (
            QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None,
                         timeout=settings.timeout)
            if settings.qdrant_url else QdrantClient(path=str(settings.qdrant_path))
        )

    def close(self) -> None:
        self.client.close()

    def exists(self) -> bool:
        return self.client.collection_exists(self.collection)

    def write_snapshot(self, chunks: list[DocumentChunk], vectors: list[list[float]],
                       signature: str, rebuild: bool = False) -> None:
        """Substituição completa explícita; não é transacional após a exclusão."""
        if not chunks or len(chunks) != len(vectors):
            raise ValueError("Chunks e vetores devem ter o mesmo tamanho positivo")
        size = len(vectors[0])
        if size == 0 or any(len(v) != size for v in vectors):
            raise ValueError("Dimensões dos vetores inválidas")
        if self.exists():
            if not rebuild:
                raise ValueError("Coleção já existe. Use ingest --rebuild para substituir o índice")
            self.client.delete_collection(self.collection)
        self.client.create_collection(self.collection, vectors_config=models.VectorParams(
            size=size, distance=models.Distance.COSINE,
        ))
        try:
            for start in range(0, len(chunks), 64):
                points = []
                for chunk, vector in zip(chunks[start:start + 64], vectors[start:start + 64], strict=True):
                    # Serialização estável evita colisões de delimitadores em nomes/textos.
                    identity = json.dumps(asdict(chunk), ensure_ascii=False, sort_keys=True)
                    points.append(models.PointStruct(
                        id=str(uuid5(NAMESPACE_URL, identity)), vector=vector,
                        payload={**asdict(chunk), "embedding_signature": signature},
                    ))
                self.client.upsert(self.collection, points=points, wait=True)
        except Exception:
            # Não deixa uma coleção parcial disponível para consultas.
            self.client.delete_collection(self.collection)
            raise

    def search(self, vector: list[float], signature: str, top_k: int,
               score_threshold: float) -> list[SearchHit]:
        if top_k <= 0:
            raise ValueError("top_k deve ser positivo")
        if not self.exists():
            raise ValueError("Índice inexistente. Execute python -m src.main ingest")
        info = self.client.get_collection(self.collection)
        params = info.config.params.vectors
        if not isinstance(params, models.VectorParams) or params.size != len(vector):
            raise ValueError("Dimensão incompatível. Reconstrua o índice")
        points, _ = self.client.scroll(self.collection, limit=1, with_payload=True)
        if not points:
            return []
        if (points[0].payload or {}).get("embedding_signature") != signature:
            raise ValueError("Modelo/instrução de embedding mudou. Reconstrua o índice")
        results = self.client.query_points(
            self.collection, query=vector, limit=top_k, score_threshold=score_threshold,
            with_payload=True,
        ).points
        hits = []
        for result in results:
            payload = result.payload or {}
            if payload.get("embedding_signature") != signature:
                raise ValueError("Índice contém embeddings incompatíveis. Reconstrua o índice")
            hits.append(SearchHit(DocumentChunk(
                source=payload["source"], page_number=payload["page_number"],
                chunk_index=payload["chunk_index"], text=payload["text"],
            ), result.score))
        return hits
