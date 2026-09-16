from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    documents_dir: Path = ROOT / "documents"
    qdrant_path: Path = ROOT / "data/qdrant"
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    collection: str = "smart_rag"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: str = field(default="", repr=False)
    embedding_model: str = "qwen/qwen3-embedding-8b"
    query_instruction: str = "Given a web search query, retrieve relevant passages that answer the query"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    batch_size: int = 16
    top_k: int = 4
    score_threshold: float = 0.3
    max_context_chars: int = 6000
    timeout: int = 180

    def __post_init__(self) -> None:
        for name in ("chunk_size", "batch_size", "top_k", "max_context_chars", "timeout"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} deve ser positivo")
        if not 0 <= self.chunk_overlap < self.chunk_size:
            raise ValueError("Exige 0 <= chunk_overlap < chunk_size")
        if not -1 <= self.score_threshold <= 1:
            raise ValueError("score_threshold deve estar entre -1 e 1")
        for name in ("collection", "openrouter_base_url", "embedding_model"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} não pode ser vazio")


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env", override=False)

    def path(name: str, default: str) -> Path:
        value = Path(os.getenv(name, default)).expanduser()
        return value if value.is_absolute() else ROOT / value

    return Settings(
        documents_dir=path("DOCUMENTS_DIR", "documents"),
        qdrant_path=path("QDRANT_PATH", "data/qdrant"),
        qdrant_url=os.getenv("QDRANT_URL", ""),
        qdrant_api_key=os.getenv("QDRANT_API_KEY", ""),
        collection=os.getenv("QDRANT_COLLECTION", "smart_rag"),
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
        embedding_model=os.getenv("EMBEDDING_MODEL", "qwen/qwen3-embedding-8b"),
        query_instruction=os.getenv("QUERY_INSTRUCTION", Settings.query_instruction),
        chunk_size=int(os.getenv("CHUNK_SIZE", "1000")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "200")),
        batch_size=int(os.getenv("BATCH_SIZE", "16")),
        top_k=int(os.getenv("TOP_K", "4")),
        score_threshold=float(os.getenv("SCORE_THRESHOLD", "0.3")),
        max_context_chars=int(os.getenv("MAX_CONTEXT_CHARS", "6000")),
        timeout=int(os.getenv("REQUEST_TIMEOUT", "180")),
    )
