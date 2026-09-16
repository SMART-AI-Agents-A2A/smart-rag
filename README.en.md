# smart_rag

[Português](README.md)

A Python 3.12 RAG without LangChain or LlamaIndex. Extraction, chunking,
embeddings, storage, retrieval, and generation are separate components.
Embeddings and generation use OpenRouter; vector storage uses Qdrant.

## Consuming the RAG

- **`src/api.py`** exposes `POST /ask` over HTTP for your backend.
- **`src/rag.py`** exposes `RAG.ask()` and `RAG.ingest()` for Python consumers.
- **`src/main.py`** provides the CLI and uses the same `RAG` component.

The API returns JSON containing the answer and its sources. `src/llm_client.py`
is only the outbound HTTP client for OpenRouter. Port 8000 belongs to the RAG;
port 6333 belongs to Qdrant. The project is not packaged for `pip install .`.

## Architecture

```text
Ingestion:
documents/*.pdf → pages → chunks → OpenRouter embeddings → Qdrant

Query:
question → OpenRouter embedding → Qdrant Top-K → context
         → OpenRouter chat → answer + cited sources
```

Default models:

| Purpose | Model |
| --- | --- |
| Embeddings | `qwen/qwen3-embedding-8b` |
| Generation | `qwen/qwen3-8b` |

Choose the generation model through `LLM_MODEL` or `ask --model`.
Configure the embedding model separately through `EMBEDDING_MODEL`.
Ollama is not a dependency.

## Requirements and installation

- Python 3.12; tests were run with Python 3.12.14.
- An OpenRouter key with model access and credits for API calls.
- Network access for embeddings and generation.
- Docker with Compose v2.24+ only when using containers.

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp -n .env.example .env
```

If `.venv` already exists, activate it and install the dependencies. `cp -n`
preserves an existing `.env`. Edit this file and set your key:

```dotenv
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_API_KEY=sua-chave
EMBEDDING_MODEL=qwen/qwen3-embedding-8b
LLM_MODEL=qwen/qwen3-8b
```

Replace `sua-chave` with your key. Direct dependencies are pinned in
`requirements.txt`: `pypdf==6.19.0`, `qdrant-client==1.19.1`,
`python-dotenv==1.2.3`, `fastapi==0.141.1`, and `uvicorn==0.53.0`.
No OpenRouter SDK is required.

## Configuration

`load_settings()` loads `.env` from the root. Environment variables override
the file; CLI arguments override their corresponding settings. Relative paths
in `.env` are resolved against the repository root. An explicit
`inspect --documents-dir` path is relative to the current working directory.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DOCUMENTS_DIR` | `documents` | PDF directory |
| `CHUNK_SIZE` | `1000` | Maximum characters per chunk |
| `CHUNK_OVERLAP` | `200` | Overlap between windows |
| `BATCH_SIZE` | `16` | Texts per embedding request |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Base URL for both APIs |
| `OPENROUTER_API_KEY` | empty | Bearer key; required when calling the API |
| `EMBEDDING_MODEL` | `qwen/qwen3-embedding-8b` | Embedding model |
| `LLM_MODEL` | `qwen/qwen3-8b` | Generation model |
| `QUERY_INSTRUCTION` | `Given a web search query, retrieve relevant passages that answer the query` | Query-only instruction; empty disables the prefix |
| `REQUEST_TIMEOUT` | `180` | Per-request timeout in seconds |
| `QDRANT_URL` | empty | Empty uses embedded storage; otherwise uses a server |
| `QDRANT_API_KEY` | empty | Qdrant server key, if required |
| `QDRANT_PATH` | `data/qdrant` | Embedded storage directory |
| `QDRANT_COLLECTION` | `smart_rag` | Index collection |
| `TOP_K` | `4` | Maximum retrieved results |
| `SCORE_THRESHOLD` | `0.3` | Minimum cosine similarity |
| `MAX_CONTEXT_CHARS` | `6000` | Context character budget, including headers |
| `QDRANT_IMAGE` | `qdrant/qdrant:latest` | Image used only by Compose |
| `QDRANT_PORT` | `6333` | Host port used only by Compose |
| `RAG_API_PORT` | `8000` | HTTP host port used only by Compose |

Size, batch size, Top-K, context budget, and timeout must be positive.
Overlap must satisfy `0 <= CHUNK_OVERLAP < CHUNK_SIZE`; the threshold must
be between -1 and 1. `inspect` needs neither an OpenRouter key nor a running database.

## CLI

Place text-based PDFs in `documents/`. Run commands from the root:

```bash
python -m src.main inspect --pages-only
python -m src.main inspect --chunk-size 1000 --overlap 200
python -m src.main inspect --documents-dir ./documents
python -m src.main ingest
python -m src.main ask "Qual é o assunto dos documentos?"
python -m src.main ask "Quais são os requisitos?" --model qwen/qwen3-8b --top-k 5 --score-threshold 0.4
python -m src.main --help
```

| Command | Result |
| --- | --- |
| `inspect` | Page/chunk counts and samples; no model calls |
| `ingest` | Indexes all PDFs; rejects an existing collection |
| `ingest --rebuild` | Replaces the entire collection |
| `ask` | Prints the answer and cited sources |

The CLI prints text, not JSON. It returns exit code 0 on success and 1 for
handled errors; invalid arguments return 2 through `argparse`. An abstention
is a valid result with exit code 0.

## HTTP API

Run ingestion before starting the API when using embedded Qdrant:

```bash
python -m src.main ingest
python -m uvicorn src.api:app --host 127.0.0.1 --port 8000 --workers 1
```

| Route | Purpose |
| --- | --- |
| `POST /ask` | Runs the RAG and returns JSON |
| `GET /health` | Returns `{"status":"ok"}`; only checks that the process responds |
| `GET /docs` | Interactive OpenAPI documentation |
| `GET /openapi.json` | API schema |

```bash
curl -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Qual é o assunto dos documentos?","model":"qwen/qwen3-8b","top_k":4,"score_threshold":0.3}'
```

| Field | Required | Validation / default |
| --- | --- | --- |
| `question` | yes | 1–10000 characters after trimming surrounding whitespace |
| `model` | no | 1–200 characters; uses `LLM_MODEL` if omitted/null |
| `top_k` | no | Integer from 1 to 100; uses `TOP_K` if omitted/null |
| `score_threshold` | no | Number from -1 to 1; uses `SCORE_THRESHOLD` if omitted/null |

Extra fields are rejected. Per-request options do not change subsequent requests'
configuration. Example response shape (illustrative content and score):

```json
{
  "text": "O documento apresenta os requisitos do projeto. [1]",
  "sources": [
    {
      "citation": 1,
      "source": "manual.pdf",
      "page_number": 2,
      "chunk_index": 0,
      "score": 0.91
    }
  ]
}
```

| HTTP | Meaning |
| --- | --- |
| 200 | Answer or abstention; abstention returns `sources: []` |
| 400 | Incompatible configuration/index or a pipeline value error |
| 409 | Index does not exist yet |
| 422 | Invalid request body |
| 502 | Provider transport/response failure, including its HTTP errors |
| 503 | Missing server API key or unavailable query service |

Errors return `{"detail": ...}`; 422 validation uses FastAPI's error list.
`/health` does not check the index, credits, or OpenRouter availability.
There is no ingestion endpoint: index through the CLI or `RAG.ingest()`.
The API has no consumer authentication; keep it on your backend's internal network.
The OpenRouter key belongs on the server, not in the `/ask` request body.

Node.js/TypeScript consumption example:

```typescript
const response = await fetch("http://localhost:8000/ask", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    question: "Qual é o assunto dos documentos?",
    model: "qwen/qwen3-8b",
  }),
});
if (!response.ok) {
  throw new Error(`RAG HTTP ${response.status}: ${await response.text()}`);
}
const result = await response.json();
console.log(result.text, result.sources);
```

## Python consumption

Run from the root, or add the root to the consumer's `PYTHONPATH`.
Ingestion must be completed before querying.

```python
from dataclasses import asdict
from src.rag import RAG

with RAG() as rag:
    response = rag.ask(
        "Qual é o assunto dos documentos?",
        model="qwen/qwen3-8b",
        top_k=4,
        score_threshold=0.3,
    )
    payload = asdict(response)
    print(payload)
```

Programmatic ingestion:

```python
from src.rag import RAG

with RAG() as rag:
    count = rag.ingest(rebuild=False)
```

`RAG(settings)` accepts a `Settings` instance; without an argument it loads
`.env`. `ask()` returns `RagResponse`; `ingest()` returns the chunk count.
The context manager closes the database; without `with`, call `rag.close()`.
Exceptions propagate to Python consumers; `IndexNotReadyError` means the index is missing.

Components are synchronous. Each `RAG` instance serializes its operations with
a lock. The API keeps one instance throughout its lifetime and closes it on
shutdown. Embedded mode allows one process per directory: use one worker and
stop the API before CLI ingestion. For separate processes, use Qdrant server;
coordinate rebuilds across processes because the lock does not protect separate instances.

## Files and contracts

| File | Responsibility |
| --- | --- |
| `src/config.py` | `Settings` and `load_settings()` |
| `src/pdf_loader.py` | `DocumentPage` and `load_pdf_pages()` |
| `src/chunker.py` | `DocumentChunk` and `chunk_pages()` |
| `src/llm_client.py` | `post_json()` with authentication, timeout, and error handling |
| `src/embeddings.py` | `Embedder.embed_documents()`, `embed_query()`, and signature |
| `src/vector_store.py` | `SearchHit`, persistence, replacement, and Qdrant search |
| `src/ingest.py` | PDF → index orchestration; returns chunk count |
| `src/retriever.py` | `retrieve()`, `Context`, and `build_context()` |
| `src/llm.py` | `Answer` and `answer_question()` |
| `src/rag.py` | Public `RAG`, `RagResponse`, `Source`, and `IndexNotReadyError` interface |
| `src/api.py` | FastAPI HTTP API, validation, and RAG lifecycle |
| `src/main.py` | CLI using the `RAG` interface |
| `tests/` | Tests with temporary PDFs, real local Qdrant, and mocked API responses |
| `Dockerfile` | Python CLI image |
| `docker-compose.yml` | Qdrant, HTTP API, and CLI containers |

Returned structures:

| Type | Fields |
| --- | --- |
| `DocumentPage` | `source: str`, `page_number: int`, `text: str` |
| `DocumentChunk` | `source: str`, `page_number: int`, `chunk_index: int`, `text: str` |
| `SearchHit` | `chunk: DocumentChunk`, `score: float` |
| `Context` | `text: str`, `sources: list[SearchHit]` |
| `Answer` | `text: str`, `sources: list[tuple[int, SearchHit]]` (internal) |
| `Source` | `citation: int`, `source: str`, `page_number: int`, `chunk_index: int`, `score: float` |
| `RagResponse` | `text: str`, `sources: list[Source]` (public) |

### Extraction and chunking

Only `*.pdf` files directly inside the directory are loaded, sorted by name.
`source` is the filename including its extension. Page numbers start at 1;
pages without text are skipped without renumbering subsequent pages. Leading
and trailing page whitespace is removed. An invalid directory or unreadable PDF raises an error.

Chunks never cross pages. `chunk_index` starts at 0 and resets on each page.
Windows advance by `chunk_size - overlap` characters; the last window may be
shorter. Whitespace-only windows are skipped, and words may be split.
Size is measured in Unicode code points, not tokens.

### Embeddings, index, and retrieval

`llm_client.py` sends HTTP JSON with `Authorization: Bearer ...`.
Embeddings use `/embeddings` and `encoding_format=float`. Each response is
reordered by `data[].index`; counts, indices, finite values, nonzero vectors,
and consistent dimensions are validated.

Documents are sent without a prefix. Questions use
`Instruct: {QUERY_INSTRUCTION}\nQuery: {question}` when an instruction is configured.
Qdrant uses explicit vectors, dimensions detected from the response, and cosine
distance. IDs are UUID5 values derived from stable serialization of chunk fields.
Payloads contain chunk fields and a provider, URL, model, and instruction signature.
Queries check the signature and dimensions before returning hits.

### Context, generation, and sources

Context contains complete passages in relevance order with identifiers such as
`[1]` and `[2]`. Passages exceeding the remaining budget are omitted; later,
smaller passages may still fit. Generation uses `/chat/completions`,
`temperature=0`, `max_tokens=1024`, and `stream=false`.

The prompt requests an answer **in Portuguese**, using only the context with
citations, and tells the model to ignore commands inside documents. The README's
language does not change the prompt language. Missing context skips generation.
Missing citations or nonexistent identifiers produce:

> Não encontrei informação suficiente nos documentos para responder.

Only identifiers actually cited and present in context appear in `Answer.sources`,
sorted with duplicate identifiers removed. Different citations can refer to
chunks from the same page. Validation does not prove that each statement is
supported by its source; hallucinations remain possible.

## Rebuilding the index

After modifying, adding, or removing PDFs, changing chunking, or changing
embedding settings, rebuild the collection:

```bash
python -m src.main ingest --rebuild
```

Changing only `LLM_MODEL`, Top-K, or the threshold does not require rebuilding.
The signature does not detect weight or internal routing changes under the same model ID.

Ingestion computes every embedding before deleting the previous index.
Reading/embedding failures and missing text preserve an existing index.
Database replacement **is not transactional**: there is no rollback after deletion.
Write failures attempt to delete the partial collection; an abrupt interruption
may leave it incomplete. Use a dedicated collection and rebuild after such a failure.

## Local Qdrant and Docker

Without `QDRANT_URL`, the client persists data in `data/qdrant/`, without Docker.
When a URL is provided, it uses the server and ignores `QDRANT_PATH`. These modes
have separate indexes; there is no automatic migration between them.

To run everything through Compose:

```bash
docker compose build app api
docker compose up -d qdrant
docker compose run --rm --no-deps app inspect
docker compose run --rm app ingest
docker compose run --rm app ask "Qual é o assunto dos documentos?" --model qwen/qwen3-8b
docker compose up -d api
curl http://localhost:8000/health
docker compose down
```

The `app` service uses the `cli` profile and runs only on demand; it does not
keep a server running. The `api` service runs Uvicorn with one worker, publishes
`127.0.0.1:${RAG_API_PORT}:8000`, and uses `/health` for its healthcheck.
A backend on the same Docker network uses `http://api:8000/ask`; outside that
network, use the published host port. `depends_on` waits for Qdrant's container
to start but does not check readiness; if connection is refused, inspect
`docker compose logs qdrant` and retry when it is ready.

Compose passes `.env` through but overrides `DOCUMENTS_DIR=/app/documents`,
`QDRANT_URL=http://qdrant:6333`, and sets `QDRANT_API_KEY` to empty. This local
server has no authentication configured and publishes its port only on `127.0.0.1`.
PDFs are mounted read-only in the CLI; the API queries the index and does not
need the PDF directory mounted. Data and snapshots use the `qdrant_storage`
and `qdrant_snapshots` volumes; `down` preserves them, while `down -v` deletes them.

For host Python with Docker Qdrant, start only `qdrant` and configure:

```dotenv
QDRANT_URL=http://localhost:6333
```

If you change `QDRANT_PORT`, also update the host URL; the internal URL is unchanged.
The Dockerfile uses Python 3.12 slim and a non-root user. `.env`, `.venv`, PDFs,
tests, and databases are not copied into the image. Rebuild the image after
changing code or dependencies. Python and Qdrant tags are mutable; pin digests
for exact reproducibility. Transitive dependencies have no lockfile.

## Tests

```bash
python -m unittest discover -s tests -v
python -m pip check
docker compose config --quiet
```

The current 16 tests cover real extraction from temporary PDFs, metadata,
chunking, Qdrant ranking/persistence, rebuilding, signatures, context, citations,
model selection, authentication, OpenRouter errors, the HTTP contract,
validation, abstention, and API database cleanup. OpenRouter responses are
mocked; these tests consume no credits and do not assess real model quality.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Missing `OPENROUTER_API_KEY` | Set it in the root `.env` |
| HTTP 401 / 403 | Check the key and model access |
| HTTP 402 | Check OpenRouter credits |
| HTTP 429 | Wait and reduce request frequency; there is no automatic retry |
| Timeout / unavailable | Check the URL/network and `REQUEST_TIMEOUT` |
| Collection already exists | Use `ingest --rebuild` to replace the index |
| Incompatible dimension or signature | Rebuild with the current embedding settings |
| No text | Check the directory, `.pdf` extension, and extractable PDF text |
| Abstention | Inspect documents, hits, threshold, and context budget |
| Local database locked | Close the other process or use Qdrant server |
| Docker permission denied | Check your user's access to the Docker daemon |

## Limitations and future equivalence

There is no OCR, reranker, incremental update, consumer authentication,
streaming, or conversation history. Each question is independent. Ingestion
keeps pages, chunks, and vectors in memory. Tables and reading order depend on
PDF extraction. Similarity is not a probability of correctness. A character
budget does not guarantee the prompt fits within the model's context window.

Document text is sent to OpenRouter for embeddings; the question and retrieved
context are sent for generation. The key stays in the runtime environment and
must not be committed. `.gitignore` also excludes PDFs and local data.

For the TypeScript implementation, preserve fields, numbering, prompts,
endpoints, cosine distance, and code-point slicing (`Array.from(text)`). If
sharing IDs, also reproduce the serialization used for UUID5. Using the same
models and server helps comparison, but `temperature=0` does not guarantee
identical responses from a remote service.
