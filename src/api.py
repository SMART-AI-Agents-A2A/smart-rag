from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .config import Settings
from .rag import IndexNotReadyError, RAG, RetrievalResponse


class RetrieveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=10000)
    top_k: int | None = Field(default=None, ge=1, le=100, strict=True)
    score_threshold: float | None = Field(default=None, ge=-1, le=1)


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        rag = RAG(settings)
        app.state.rag = rag
        try:
            yield
        finally:
            rag.close()

    app = FastAPI(title="smart_rag", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/retrieve", response_model=RetrievalResponse)
    def retrieve(body: RetrieveRequest, request: Request) -> RetrievalResponse:
        rag: RAG = request.app.state.rag
        if not rag.settings.openrouter_api_key.strip():
            raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY não configurada no servidor")
        try:
            return rag.retrieve(body.question, top_k=body.top_k,
                           score_threshold=body.score_threshold)
        except IndexNotReadyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail="Falha ao processar resposta do provedor") from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Serviço de consulta indisponível") from exc

    return app


app = create_app()
