import math

from .config import Settings
from .llm_client import post_json


class Embedder:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def signature(self) -> str:
        return "\n".join(("openrouter", self.settings.openrouter_base_url.rstrip("/"),
                          self.settings.embedding_model, self.settings.query_instruction))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(not text.strip() for text in texts):
            raise ValueError("Não é possível gerar embedding de texto vazio")
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.settings.batch_size):
            batch = texts[start : start + self.settings.batch_size]
            result = post_json(self.settings.openrouter_base_url, "/embeddings", {
                "model": self.settings.embedding_model, "input": batch, "encoding_format": "float",
            }, self.settings.timeout, api_key=self.settings.openrouter_api_key)
            values = result.get("data")
            if not isinstance(values, list) or len(values) != len(batch):
                raise RuntimeError("OpenRouter retornou quantidade incorreta de embeddings")
            if any(not isinstance(item, dict) or type(item.get("index")) is not int for item in values):
                raise RuntimeError("OpenRouter retornou índices inválidos")
            if sorted(item["index"] for item in values) != list(range(len(batch))):
                raise RuntimeError("OpenRouter retornou índices duplicados ou ausentes")
            for item in sorted(values, key=lambda item: item["index"]):
                vector = item.get("embedding")
                if (not isinstance(vector, list) or not vector
                    or any(type(v) not in (int, float) or not math.isfinite(v) for v in vector)
                    or not any(vector)):
                    raise RuntimeError("Embedding inválido, vazio ou nulo")
                if vectors and len(vector) != len(vectors[0]):
                    raise RuntimeError("Dimensões inconsistentes nos embeddings")
                vectors.append([float(v) for v in vector])
        return vectors

    def embed_query(self, question: str) -> list[float]:
        if not question.strip():
            raise ValueError("A pergunta não pode ser vazia")
        instruction = self.settings.query_instruction
        text = f"Instruct: {instruction}\nQuery: {question}" if instruction else question
        return self.embed_documents([text])[0]
