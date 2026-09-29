# smart_rag

[Português](README.ptbr.md)

A **document retrieval** service for a larger backend. It indexes PDFs and returns relevant passages with sources for each question. **It does not generate answers**: the consuming backend chooses its LLM and uses the retrieved context to ground the final answer.

**RAG type:** dense semantic retrieval with character windows and Top-K vector search. The consuming backend handles generation, which completes the RAG flow. There is no keyword search, hybrid retrieval, reranking, or agent. The vector database is **Qdrant**, used locally through the embedded `qdrant-client` mode or as a server through `QDRANT_URL`; the similarity metric is cosine.

## How it works

```text
Ingestion: documents/*.pdf → pages → chunks → embeddings (OpenRouter) → Qdrant
Query:     question → embedding (OpenRouter) → Qdrant Top-K search
           → score filter → context budget → context + chunks
Application: consuming backend → its LLM → final answer to the user
```

1. `src/pdf_loader.py` reads `*.pdf` files directly from `DOCUMENTS_DIR`, sorted by name. It extracts text with `pypdf`, skips empty pages, and preserves the original page numbers starting at 1. There is no OCR.
2. `src/chunker.py` divides each page into windows of up to `CHUNK_SIZE` Unicode characters, sharing `CHUNK_OVERLAP` characters between windows. Chunks never cross pages; `chunk_index` starts at 0 on each page. Windows may split words.
3. `src/embeddings.py` sends texts in batches of `BATCH_SIZE` to OpenRouter's `POST /embeddings`. Documents receive no prefix; when configured, the question uses `Instruct: {QUERY_INSTRUCTION}\nQuery: {question}`. The client validates vector counts, indices, dimensions, and values.
4. `src/vector_store.py` writes vectors to Qdrant using cosine distance. Each point stores text, PDF filename, page number, chunk index, and an embedding configuration signature. Queries check the signature and vector dimension to prevent use of an incompatible index.
5. `src/retriever.py` requests up to `TOP_K` results above `SCORE_THRESHOLD`, ordered by relevance. It assembles `context` from **complete** passages numbered `[1]`, `[2]`, etc., within `MAX_CONTEXT_CHARS` characters, including headers. If a passage does not fit, a smaller later one may still be included. `chunks` contains exactly the included passages, with text, source, page, and score.

The backend receives the user's message, resolves conversation references when needed, calls `POST /retrieve`, and sends the question and context to **its own** generation model. Treat PDF text as data, not instructions. This service has no `/ask`, `RAG.ask()`, `LLM_MODEL`, or `/chat/completions` calls.

## Installation and configuration

Requires Python 3.12, an OpenRouter key with access to the embedding model, and network access. Docker is optional. From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp -n .env.example .env
```

Set `OPENROUTER_API_KEY` in `.env`. `cp -n` preserves an existing file; environment variables take precedence over `.env`. Keep the key on the server, never in a request body. LangChain, LlamaIndex, and an OpenRouter SDK are not required.

### Versions used

| Component | Version in this project | Purpose |
| --- | --- | --- |
| Python | 3.12; `python:3.12-slim` image | Pipeline, CLI, and API |
| `pypdf` | 6.19.0 | PDF text extraction |
| `qdrant-client` | 1.19.1 | Embedded Qdrant or server access |
| `python-dotenv` | 1.2.3 | `.env` loading |
| `fastapi` | 0.141.1 | HTTP API and validation |
| `uvicorn` | 0.53.0 | API server |
| Qdrant server | `qdrant/qdrant:latest` | Vector database in Compose; version not pinned |
| Embedding model | `qwen/qwen3-embedding-8b` | Default OpenRouter model ID; remote revision not pinned |

Direct library versions are pinned in `requirements.txt`; transitive dependencies and the Qdrant image are not pinned.

### `.env` parameters

| Variable | Type / default | Effect |
| --- | --- | --- |
| `DOCUMENTS_DIR` | path / `documents` | Directory read during ingestion; only top-level `*.pdf` files |
| `CHUNK_SIZE` | integer / `1000` | Maximum characters per chunk |
| `CHUNK_OVERLAP` | integer / `200` | Characters repeated between windows on the same page |
| `BATCH_SIZE` | integer / `16` | Texts sent per embedding request |
| `OPENROUTER_BASE_URL` | URL / `https://openrouter.ai/api/v1` | Base URL used to build the `/embeddings` endpoint |
| `OPENROUTER_API_KEY` | string / empty | Bearer key required for ingestion and queries |
| `EMBEDDING_MODEL` | string / `qwen/qwen3-embedding-8b` | Model used to vectorize documents and questions |
| `QUERY_INSTRUCTION` | string / `Given a web search query, retrieve relevant passages that answer the query` | Instruction added only to questions; empty disables it |
| `REQUEST_TIMEOUT` | integer / `180` | Maximum seconds per OpenRouter call; also used by the Qdrant server client |
| `QDRANT_URL` | URL / empty | Empty selects embedded Qdrant; a value selects a server |
| `QDRANT_API_KEY` | string / empty | Optional credential for a Qdrant server |
| `QDRANT_PATH` | path / `data/qdrant` | Embedded database directory; ignored when `QDRANT_URL` is set |
| `QDRANT_COLLECTION` | string / `smart_rag` | Vector collection name |
| `TOP_K` | integer / `4` | Maximum results requested from Qdrant before applying the context budget |
| `SCORE_THRESHOLD` | number / `0.3` | Minimum cosine similarity for accepting a result |
| `MAX_CONTEXT_CHARS` | integer / `6000` | Context character limit, including headers and separators |
| `QDRANT_IMAGE` | string / `qdrant/qdrant:latest` | Qdrant image used only by Compose |
| `QDRANT_PORT` | integer / `6333` | Qdrant port published on the host by Compose |
| `RAG_API_PORT` | integer / `8000` | API port published on the host by Compose |

Size, batch size, Top-K, context budget, and timeout must be positive; `0 <= CHUNK_OVERLAP < CHUNK_SIZE`, and the threshold must be between -1 and 1. Relative paths from `.env` resolve against the project root. An explicit `inspect --documents-dir` path is relative to the current working directory.

## Ingestion and CLI queries

Place PDFs with extractable text in `documents/` and run:

```bash
python -m src.main inspect --pages-only
python -m src.main inspect --chunk-size 1000 --overlap 200
python -m src.main ingest
python -m src.main retrieve "What are the requirements?"
python -m src.main retrieve "What are the requirements?" --top-k 5 --score-threshold 0.4
```

`inspect` shows pages and chunk samples without calling OpenRouter or opening the database. `ingest` indexes all PDFs and refuses to replace an existing collection. `retrieve` prints JSON in the same shape as the API. Exit codes: 0 for success, including empty results; 1 for a handled error; 2 for invalid arguments.

| CLI option | Effect |
| --- | --- |
| `inspect --pages-only` | Shows pages without generating chunk samples |
| `inspect --documents-dir PATH` | Overrides `DOCUMENTS_DIR` for this inspection only |
| `inspect --chunk-size N` | Overrides `CHUNK_SIZE` for this inspection only |
| `inspect --overlap N` | Overrides `CHUNK_OVERLAP` for this inspection only |
| `ingest --rebuild` | Replaces the whole collection after preparing new vectors |
| `retrieve --top-k N` | Overrides `TOP_K` for this query |
| `retrieve --score-threshold N` | Overrides `SCORE_THRESHOLD` for this query |

Rebuild the index after changing PDFs, chunking, or embedding settings:

```bash
python -m src.main ingest --rebuild
```

Ingestion reads and vectorizes everything before deleting the previous index, so failures during those stages preserve it. **Replacement is not transactional** after deletion: a failure or interruption can leave the collection incomplete. Coordinate rebuilds with queries. Changing Top-K, threshold, or context budget does not require reindexing. The signature identifies the provider, URL, model, and instruction, but does not detect internal weight changes under the same model ID.

## HTTP API

With embedded Qdrant, finish ingestion before starting the API and use only one process for the same database directory:

```bash
python -m uvicorn src.api:app --host 127.0.0.1 --port 8000 --workers 1
```

| Route | Result |
| --- | --- |
| `POST /retrieve` | Returns context and chunks with sources |
| `GET /health` | `{"status":"ok"}`; checks process responsiveness only |
| `GET /docs` / `GET /openapi.json` | Interactive documentation and OpenAPI schema |

```bash
curl -X POST http://localhost:8000/retrieve \
  -H 'Content-Type: application/json' \
  -d '{"question":"What are the requirements?","top_k":4,"score_threshold":0.3}'
```

| `POST /retrieve` field | Type and rule | Effect |
| --- | --- | --- |
| `question` | Required string; 1 to 10000 characters after trimming outer whitespace | Question vectorized for the search |
| `top_k` | Optional integer from 1 to 100 | Overrides `TOP_K` for this request |
| `score_threshold` | Optional number between -1 and 1 | Overrides `SCORE_THRESHOLD` for this request |

Omitting an option or sending `null` uses its configured default. Extra fields, including `model`, are rejected. Per-request options do not change subsequent requests.

Illustrative response (the `página` header is emitted literally by the implementation):

```json
{
  "context": "[1] PDF: \"manual.pdf\" | página: 2 | chunk: 0\nThe project requires Python 3.12.",
  "chunks": [
    {
      "reference": 1,
      "source": "manual.pdf",
      "page_number": 2,
      "chunk_index": 0,
      "score": 0.91,
      "text": "The project requires Python 3.12."
    }
  ]
}
```

With no suitable passages, the API returns HTTP 200 with `{"context":"","chunks":[]}`. The threshold and context budget can reduce the number of returned chunks below Top-K. A similarity score is not a probability of correctness.

| HTTP | Meaning |
| --- | --- |
| 200 | Retrieval completed, including an empty result |
| 400 | Invalid pipeline value or incompatible configuration/index |
| 409 | Index does not exist |
| 422 | Invalid request body |
| 502 | OpenRouter transport or response failure |
| 503 | Missing server key or unavailable service |

Errors use `{"detail": ...}`; 422 validation follows FastAPI's format. `/health` does not check the index, credits, or OpenRouter. There is no ingestion endpoint or consumer authentication; keep the API on the backend's internal network.

Node.js/TypeScript consumption example:

```typescript
const response = await fetch("http://localhost:8000/retrieve", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ question: "What are the requirements?" }),
});
if (!response.ok) throw new Error(`RAG HTTP ${response.status}: ${await response.text()}`);
const { context, chunks } = await response.json();
// Use context in your LLM prompt and chunks to display sources.
```

## Python usage

Run from the repository root or add it to `PYTHONPATH`:

```python
from dataclasses import asdict
from src.rag import RAG

with RAG() as rag:
    result = rag.retrieve("What are the requirements?", top_k=4)
    payload = asdict(result)
```

`RAG(settings)` accepts a `Settings` instance; without an argument it loads `.env`. `RAG.ingest(rebuild=False)` returns the chunk count. `retrieve()` returns `RetrievalResponse(context, chunks)` and propagates exceptions; `IndexNotReadyError` means the collection is missing. Without `with`, call `rag.close()`. Each instance serializes operations with a lock; separate processes do not share that lock.

## Qdrant and Docker Compose

Without `QDRANT_URL`, embedded Qdrant persists in `data/qdrant/`. With a URL, the client uses a server; the two modes have independent indexes. To use Docker Qdrant from host Python, set `QDRANT_URL=http://localhost:6333` and ingest in that mode.

```bash
docker compose build app api
docker compose up -d qdrant
docker compose run --rm app ingest
docker compose up -d api
curl http://localhost:8000/health
docker compose run --rm app retrieve "What are the requirements?"
docker compose down
```

The `app` service is an on-demand CLI; `api` runs one worker. On the Compose network, the backend calls `http://api:8000/retrieve`; from the host, use `http://localhost:8000/retrieve`. Compose mounts PDFs only in the CLI, publishes ports on `127.0.0.1`, and persists data in the `qdrant_storage` and `qdrant_snapshots` volumes. `docker compose down` preserves the volumes; `down -v` removes them. `depends_on` waits for the Qdrant container to start, not for service readiness.

## Tests and limitations

```bash
python -m unittest discover -s tests -v
python -m pip check
docker compose config --quiet
```

Tests use temporary PDFs, local Qdrant, and mocked OpenRouter responses; they consume no credits and do not assess model quality. The project has no OCR, reranking, incremental updates, conversation history, or streaming. Ingestion holds pages, chunks, and vectors in memory; tables and reading order depend on PDF extraction. A character limit does not guarantee that the context fits the consuming LLM's token window.

Document text and questions are sent to OpenRouter for embeddings. This service **does not** send retrieved context to a generation model. Keep keys, PDFs, and local data out of Git.
