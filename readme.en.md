# smart_rag

[Português](README.md)

Document retrieval service for a larger backend. It accepts a question, searches
Qdrant, and returns context with sources. **It does not generate answers.**
The consuming project chooses its LLM and uses the passages to ground its own answer.

## Architecture

```text
documents/*.pdf → pages → chunks → Qwen embeddings (OpenRouter) → Qdrant

Backend → question → POST /retrieve → question embedding → Qdrant Top-K
        ← context + chunks + metadata

Backend → its own LLM → final answer
```

- `src/api.py`: HTTP interface `POST /retrieve`.
- `src/rag.py`: Python interface `RAG.retrieve()` and `RAG.ingest()`.
- `src/main.py`: `inspect`, `ingest`, and `retrieve` CLI commands.
- `src/llm_client.py`: HTTP transport used only by the embedding API.

The configured model is `qwen/qwen3-embedding-8b`. There is no generation,
chat, `LLM_MODEL`, or `/ask` endpoint. No calls are made to `/chat/completions`.

## Responsibilities in the larger application

| Stage | This service | Consuming backend |
| --- | --- | --- |
| Preparation | Extracts PDFs, creates chunks, and stores embeddings in Qdrant | Provides documents and coordinates ingestion |
| Question | Receives the question at `/retrieve` and embeds it | Receives the user's message and resolves references to conversation history |
| Retrieval | Searches passages and returns `context`, `chunks`, and metadata | Decides how to use context and handles empty results |
| Generation | Returns retrieved data | Sends the question and context to its own LLM before generating the answer |
| Delivery | Provides PDF, page, text, and score for passages | Presents the final answer and its sources to the user |

The complete RAG combines retrieval and generation. This repository supplies
retrieval; the consuming backend implements generation grounded in that data.

## Technologies used

### Language and libraries

| Technology | Version / source | Project usage |
| --- | --- | --- |
| Python | 3.12; validated with 3.12.14 | Pipeline implementation and Python/HTTP interfaces |
| pypdf | 6.19.0 | Text and metadata extraction from individual PDF pages |
| qdrant-client | 1.19.1 | Access to embedded or server Qdrant; vector storage and search |
| python-dotenv | 1.2.3 | Loading settings from `.env` |
| FastAPI | 0.141.1 | `POST /retrieve`, HTTP validation, and OpenAPI documentation |
| Uvicorn | 0.53.0 | ASGI server running the API |
| Pydantic | Transitive dependency of FastAPI/qdrant-client | Request body validation in `src/api.py` |
| Python standard library | Included in Python 3.12 | `dataclasses`, `pathlib`, `urllib.request`, `json`, `uuid`, `argparse`, and synchronization |
| unittest / unittest.mock | Included in Python 3.12 | Automated tests and mocked embedding responses |

Direct dependency versions are pinned in `requirements.txt`.
Transitive dependencies are not individually pinned.

### Model, services, and runtime

| Technology | Current configuration | Project usage |
| --- | --- | --- |
| Qwen3 Embedding 8B | `qwen/qwen3-embedding-8b` | Embedding documents and questions |
| OpenRouter | `https://openrouter.ai/api/v1/embeddings` | Remote embedding model access over HTTP with a Bearer key |
| Qdrant | Embedded or `qdrant/qdrant:latest` image | Vector/metadata persistence and Top-K retrieval using cosine similarity |
| Docker | `python:3.12-slim` base image | Packaging the API and CLI |
| Docker Compose | v2.24+ | Running `qdrant`, `api`, and `app`, networking, and persistent volumes |
| HTTP / JSON / OpenAPI | `/retrieve`, `/docs`, and `/openapi.json` | Integration contract for the consuming backend |

Embedded Qdrant uses the Python client's implementation; the server image
version is independent of `qdrant-client`. `latest` and `3.12-slim` are mutable
tags. Docker is optional when running Python with embedded Qdrant.
Node.js/TypeScript is shown as a consumption example, not a service dependency.

## Installation

Requires Python 3.12 and an OpenRouter key with model access and credits.
Embeddings require network access. Docker/Compose v2.24+ is optional.
From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp -n .env.example .env
```

If `.venv` already exists, activate it. `cp -n` preserves an existing `.env`.
Set the key in `.env`; never send it in the request body to the RAG.

```dotenv
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_API_KEY=your-key
EMBEDDING_MODEL=qwen/qwen3-embedding-8b
```

Direct dependencies: `pypdf==6.19.0`, `qdrant-client==1.19.1`,
`python-dotenv==1.2.3`, `fastapi==0.141.1`, `uvicorn==0.53.0`.
No LangChain, LlamaIndex, or OpenRouter SDK. Installation through `pip install .` is not configured.

## Configuration

`.env` is loaded from the root; environment variables override it.
Explicit CLI/HTTP/Python options override their corresponding defaults.
Relative `.env` paths resolve against the root; `inspect --documents-dir`
resolves against the current working directory.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DOCUMENTS_DIR` | `documents` | PDF directory |
| `CHUNK_SIZE` | `1000` | Characters per chunk |
| `CHUNK_OVERLAP` | `200` | Character overlap |
| `BATCH_SIZE` | `16` | Texts per embedding call |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Base URL |
| `OPENROUTER_API_KEY` | `—` | Bearer key; empty by default |
| `EMBEDDING_MODEL` | `qwen/qwen3-embedding-8b` | Embedding model |
| `QUERY_INSTRUCTION` | `Given a web search query, retrieve relevant passages that answer the query` | Query prefix; empty disables it |
| `REQUEST_TIMEOUT` | `180` | Timeout in seconds per call |
| `QDRANT_URL` | `—` | Empty: embedded; set: server |
| `QDRANT_API_KEY` | `—` | Qdrant key; empty by default |
| `QDRANT_PATH` | `data/qdrant` | Embedded database directory |
| `QDRANT_COLLECTION` | `smart_rag` | Index collection |
| `TOP_K` | `4` | Maximum hits before applying the context budget |
| `SCORE_THRESHOLD` | `0.3` | Minimum cosine similarity |
| `MAX_CONTEXT_CHARS` | `6000` | Budget including headers |
| `QDRANT_IMAGE` | `qdrant/qdrant:latest` | Compose image |
| `QDRANT_PORT` | `6333` | Qdrant host port (Compose) |
| `RAG_API_PORT` | `8000` | RAG host port (Compose) |

Size, batch size, Top-K, budget, and timeout must be positive.
`0 <= CHUNK_OVERLAP < CHUNK_SIZE`; threshold between -1 and 1.
`inspect` works without a key and does not open the database.

## Ingestion and CLI

Place PDFs in `documents/` and run from the root:

```bash
python -m src.main inspect --pages-only
python -m src.main inspect --chunk-size 1000 --overlap 200
python -m src.main inspect --documents-dir ./documents
python -m src.main ingest
python -m src.main retrieve "Quais são os requisitos?"
python -m src.main retrieve "Quais são os requisitos?" --top-k 5 --score-threshold 0.4
python -m src.main --help
```

`inspect` prints samples. `ingest` indexes all PDFs and rejects an existing
collection. `retrieve` prints JSON matching the API response. Exit codes:
0 for success (including no results), 1 for handled errors, and 2 for invalid
arguments. The `ask` command no longer exists.

## HTTP API

With embedded Qdrant, complete ingestion before starting the API.
Use one worker and stop the API before another CLI ingestion.

```bash
python -m uvicorn src.api:app --host 127.0.0.1 --port 8000 --workers 1
```

| Route | Purpose |
| --- | --- |
| `POST /retrieve` | Retrieves passages and context |
| `GET /health` | Returns `{"status":"ok"}`; process liveness only |
| `GET /docs` | Interactive documentation |
| `GET /openapi.json` | OpenAPI schema |

Only the question is required:

```bash
curl -X POST http://localhost:8000/retrieve \
  -H 'Content-Type: application/json' \
  -d '{"question":"Quais são os requisitos?"}'
```

| Field | Rule |
| --- | --- |
| `question` | Required; 1–10000 characters after trimming outer whitespace |
| `top_k` | Optional; integer from 1 to 100, defaults to `TOP_K` |
| `score_threshold` | Optional; number between -1 and 1, defaults to `SCORE_THRESHOLD` |

Omitted or null options use defaults. Extra fields, including `model`, are
rejected. Requests do not change global settings. Response shape; the text
and score below are illustrative:

```json
{
  "context": "[1] PDF: \"manual.pdf\" | página: 2 | chunk: 0\nO projeto requer Python 3.12.",
  "chunks": [
    {
      "reference": 1,
      "source": "manual.pdf",
      "page_number": 2,
      "chunk_index": 0,
      "score": 0.91,
      "text": "O projeto requer Python 3.12."
    }
  ]
}
```

`context` concatenates passages with headers. `chunks` contains exactly the
same passages as structured data; `reference` corresponds to `[1]`, `[2]`, etc.
The response can contain fewer than Top-K passages: the threshold and context
budget filter them. Only complete chunks fitting the budget are returned;
if one does not fit, a later smaller passage may still be included.
No results returns HTTP 200 with `{"context":"","chunks":[]}`.
There is no generated answer or abstention message.

| HTTP | Meaning |
| --- | --- |
| 200 | Retrieval completed, including no results |
| 400 | Incompatible configuration/index or invalid pipeline value |
| 409 | Missing index |
| 422 | Invalid request |
| 502 | Embedding provider transport/response failure |
| 503 | Missing server API key or unavailable service |

Errors use `{"detail": ...}`; 422 validation returns a FastAPI error list.
`/health` does not check the index, credits, or OpenRouter. There is no ingestion
endpoint or consumer authentication. Keep the service on the backend's internal network.

## Backend consumption

```typescript
const response = await fetch("http://localhost:8000/retrieve", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ question: "Quais são os requisitos?" }),
});
if (!response.ok) {
  throw new Error(`RAG HTTP ${response.status}: ${await response.text()}`);
}
const { context, chunks } = await response.json();
```

The backend uses `context` in its own LLM prompt or builds context from `chunks`.
It also controls history, language, model, final answers, and source display.
Retrieved documents are data, not instructions to execute.

## Python consumption

```python
from dataclasses import asdict
from src.rag import RAG

with RAG() as rag:
    result = rag.retrieve("Quais são os requisitos?")
    payload = asdict(result)
```

```python
from src.rag import RAG

with RAG() as rag:
    count = rag.ingest(rebuild=False)
```

Run from the root or include it in `PYTHONPATH`. `RAG(settings)` accepts `Settings`;
without an argument it loads `.env`. `retrieve()` accepts optional `top_k` and
`score_threshold` and returns `RetrievalResponse`. `ingest()` returns the chunk count.
Without `with`, close using `rag.close()`. Exceptions propagate;
`IndexNotReadyError` indicates a missing index.

Each instance serializes operations with a lock. The API maintains one instance
and closes it on shutdown. Embedded storage allows one process per directory.
For multiple processes use Qdrant server; the lock does not coordinate separate instances.

## Components and contracts

| File | Purpose |
| --- | --- |
| `src/config.py` | Configuration and validation |
| `src/pdf_loader.py` | PDF → DocumentPage |
| `src/chunker.py` | Pages → DocumentChunk |
| `src/llm_client.py` | Authenticated HTTP JSON for embeddings |
| `src/embeddings.py` | Text and question vectors |
| `src/vector_store.py` | Persistence, signature, and cosine search |
| `src/ingest.py` | Ingestion orchestration |
| `src/retriever.py` | Top-K and context assembly |
| `src/rag.py` | Public Python interface |
| `src/api.py` | Public HTTP interface |
| `src/main.py` | CLI |

```text
DocumentPage: source, page_number, text
DocumentChunk: source, page_number, chunk_index, text
SearchHit: chunk, score
Context: text, sources
RetrievedChunk: reference, source, page_number, chunk_index, score, text
RetrievalResponse: context, chunks
```

PDFs are read by name, only matching `*.pdf` directly in the directory. Pages
start at 1; empty pages are skipped without renumbering later pages. `source`
includes the extension. Invalid directories/unreadable PDFs raise errors. No OCR.

Chunks do not cross pages; `chunk_index` starts at 0 per page. Windows advance
by `chunk_size - overlap` Unicode characters (not tokens), may split words, and
skip whitespace-only windows. The last window may be shorter.

Embeddings use `POST /embeddings`, Bearer authentication, and `encoding_format=float`.
Responses are ordered by `data[].index`. Counts, indices, dimensions, finite
values, and nonzero vectors are validated. Documents receive no prefix;
questions use `Instruct: {QUERY_INSTRUCTION}\nQuery: {question}`.

Qdrant uses detected dimensions, cosine distance, and UUID5 IDs derived from
stable serialization of chunk fields. Payloads store those fields and the
provider/URL/model/instruction signature. Search checks signature and dimensions.

## Rebuilding

```bash
python -m src.main ingest --rebuild
```

Rebuild after changing PDFs, chunking, or embedding settings. Changing Top-K,
threshold, or budget does not require rebuilding. Weight or routing changes
under the same model ID are not detected by the signature.

Reading and embeddings finish before deleting the previous index. Failures at
those stages or missing text preserve it. Replacement **is not transactional**:
there is no rollback after deletion. Write failures attempt to remove the partial
collection; abrupt interruptions may leave it incomplete. Coordinate rebuilds
to avoid concurrent queries and use a dedicated collection.

## Docker and Qdrant

```bash
docker compose build app api
docker compose up -d qdrant
docker compose run --rm app ingest
docker compose up -d api
curl http://localhost:8000/health
docker compose run --rm app retrieve "Quais são os requisitos?"
docker compose down
```

The `api` service runs Uvicorn with one worker. `app` uses the `cli` profile and
runs on demand. A backend on the same Docker network uses `http://api:8000/retrieve`;
on the host use `http://localhost:8000/retrieve`. Set the port with `RAG_API_PORT`.
Port 6333 belongs to the database, not the retrieval service.

Compose passes `.env` and overrides `DOCUMENTS_DIR=/app/documents`,
`QDRANT_URL=http://qdrant:6333`, and `QDRANT_API_KEY` to empty. The CLI mounts PDFs
read-only; the API does not need that directory. Ports are published on
127.0.0.1. Compose Qdrant has no authentication configured. Its `depends_on`
checks startup, not readiness: inspect logs and retry if it is still starting.

The `qdrant_storage` and `qdrant_snapshots` volumes persist after `down`;
`down -v` deletes the data. The Dockerfile uses a non-root user and Python 3.12 slim.
`.env`, `.venv`, PDFs, tests, and databases are excluded from the image. Rebuild
after code/dependency changes. Tags are mutable; pin digests for exact
reproducibility. Transitive dependencies have no lockfile.

Without `QDRANT_URL`, Python uses embedded storage in `data/qdrant`. To use
Docker Qdrant from the host, configure the following. Embedded and server modes
do not share indexes; ingest in the selected mode.

```dotenv
QDRANT_URL=http://localhost:6333
```

If you change `QDRANT_PORT`, update this host URL. The internal URL is unchanged.

## Tests and troubleshooting

```bash
python -m unittest discover -s tests -v
python -m pip check
docker compose config --quiet
```

Tests use temporary PDFs, real local Qdrant, and mocked embeddings. They cover
extraction, chunks, ranking, persistence, rebuilding, signatures, budgets,
authentication, the HTTP contract, empty results, and database cleanup. They
verify that calls are embedding-only. They do not assess model quality or
consume credits. Validation Python version: 3.12.14.

- Missing key: set `OPENROUTER_API_KEY`.
- OpenRouter 401/403: key/access; 402: credits; 429: wait and reduce calls.
  The retrieval HTTP API reports provider failures as 502.
- There is no automatic retry; timeout uses `REQUEST_TIMEOUT`.
- Incompatible/existing index: use `ingest --rebuild` when replacing it.
- No text: check directory, extension, and whether the PDF contains extractable text.
- No passages: check threshold, documents, and `MAX_CONTEXT_CHARS`.
- Embedded database locked: close the other process or use a server.
- Docker permission denied: check the user's access to the daemon.

## Limitations and migration

Consumers must migrate from `/ask` to `/retrieve`, from `RAG.ask()` to
`RAG.retrieve()`, and from generated answers to `context`/`chunks`. Do not send `model`.
Updating retrieval code does not require reindexing if embeddings have not changed.

There is no OCR, reranker, incremental ingestion, history, or streaming. Pages,
chunks, and vectors remain in memory during ingestion. Similarity is not a
probability of correctness. Reading order and tables depend on the PDF.
The character budget does not guarantee a fit in the consumer LLM's context window.

Documents and questions are sent to OpenRouter for embeddings. This service
sends no context to a generation LLM. Keys, PDFs, and local data are excluded
from Git; the key must not be committed.

For TypeScript equivalence, preserve metadata, numbering, the query prefix,
cosine distance, and Unicode slicing with `Array.from(text)`. If sharing IDs,
reproduce the serialization used by UUID5.
