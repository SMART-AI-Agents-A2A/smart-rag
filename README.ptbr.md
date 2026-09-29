# smart_rag

[English](readme.en.md)

Serviço de **recuperação de documentos** para um backend maior. Indexa PDFs e devolve trechos relevantes com fontes para cada pergunta. **Não gera respostas**: o backend consumidor escolhe seu LLM e usa o contexto recuperado para fundamentar a resposta final.

**Tipo de RAG:** recuperação semântica densa (*dense retrieval*) com janelas de caracteres e busca vetorial Top-K. A geração, que completa o fluxo RAG, pertence ao backend consumidor. Não há busca por palavras-chave, recuperação híbrida, reranking nem agente. O banco vetorial é **Qdrant**, usado localmente pelo `qdrant-client` em modo embutido ou como servidor via `QDRANT_URL`; a métrica é similaridade de cosseno.

## Como funciona

```text
Ingestão: documents/*.pdf → páginas → chunks → embeddings (OpenRouter) → Qdrant
Consulta: pergunta → embedding (OpenRouter) → busca Top-K no Qdrant
         → filtro de score → orçamento de contexto → context + chunks
Aplicação: backend consumidor → seu LLM → resposta final ao usuário
```

1. `src/pdf_loader.py` lê arquivos `*.pdf` diretamente em `DOCUMENTS_DIR`, em ordem de nome. Extrai texto com `pypdf`, ignora páginas vazias e preserva a numeração original, iniciada em 1. Não há OCR.
2. `src/chunker.py` divide cada página em janelas de até `CHUNK_SIZE` caracteres Unicode, com `CHUNK_OVERLAP` caracteres compartilhados. Chunks não cruzam páginas; `chunk_index` começa em 0 em cada página. As janelas podem cortar palavras.
3. `src/embeddings.py` envia textos em lotes de `BATCH_SIZE` para `POST /embeddings` da OpenRouter. Documentos não recebem prefixo; a pergunta usa `Instruct: {QUERY_INSTRUCTION}\nQuery: {pergunta}` quando há instrução. Quantidade, índices, dimensões e valores dos vetores são validados.
4. `src/vector_store.py` grava os vetores no Qdrant com distância de cosseno. Cada ponto contém texto, PDF, página, índice do chunk e assinatura da configuração de embeddings. A consulta verifica assinatura e dimensão para evitar um índice incompatível.
5. `src/retriever.py` busca até `TOP_K` resultados acima de `SCORE_THRESHOLD`, em ordem de relevância. Monta `context` com trechos **inteiros**, numerados `[1]`, `[2]` etc., dentro de `MAX_CONTEXT_CHARS` caracteres, incluindo cabeçalhos. Se um trecho não couber, outro menor pode entrar. `chunks` contém exatamente os trechos incluídos, com texto, origem, página e score.

O backend recebe a mensagem do usuário, resolve referências ao histórico quando necessário, chama `POST /retrieve` e envia pergunta e contexto ao **seu** modelo de geração. Trate o texto dos PDFs como dado, não como instrução. Este serviço não possui `/ask`, `RAG.ask()`, `LLM_MODEL` nem chamadas a `/chat/completions`.

## Instalação e configuração

Requer Python 3.12, chave OpenRouter com acesso ao modelo de embeddings e rede. Docker é opcional. Na raiz do repositório:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp -n .env.example .env
```

Defina `OPENROUTER_API_KEY` em `.env`. `cp -n` preserva um arquivo existente; variáveis do ambiente prevalecem sobre o `.env`. A chave fica no servidor, nunca no corpo da requisição. LangChain, LlamaIndex e SDK da OpenRouter não são necessários.

### Versões usadas

| Componente | Versão no projeto | Uso |
| --- | --- | --- |
| Python | 3.12; imagem `python:3.12-slim` | Pipeline, CLI e API |
| `pypdf` | 6.19.0 | Extração de texto dos PDFs |
| `qdrant-client` | 1.19.1 | Qdrant embutido ou acesso ao servidor |
| `python-dotenv` | 1.2.3 | Leitura do `.env` |
| `fastapi` | 0.141.1 | API HTTP e validação |
| `uvicorn` | 0.53.0 | Servidor da API |
| Qdrant servidor | `qdrant/qdrant:latest` | Banco vetorial no Compose; versão não fixada |
| Modelo de embeddings | `qwen/qwen3-embedding-8b` | Identificador padrão na OpenRouter; revisão remota não fixada |

As versões das bibliotecas diretas estão fixadas em `requirements.txt`; dependências transitivas e a imagem Qdrant não possuem versão fixa.

### Parâmetros do `.env`

| Variável | Tipo / padrão | Efeito |
| --- | --- | --- |
| `DOCUMENTS_DIR` | caminho / `documents` | Diretório lido na ingestão; somente arquivos `*.pdf` no nível superior |
| `CHUNK_SIZE` | inteiro / `1000` | Máximo de caracteres por chunk |
| `CHUNK_OVERLAP` | inteiro / `200` | Caracteres repetidos entre janelas da mesma página |
| `BATCH_SIZE` | inteiro / `16` | Quantidade de textos enviada por chamada de embeddings |
| `OPENROUTER_BASE_URL` | URL / `https://openrouter.ai/api/v1` | Base usada para montar o endpoint `/embeddings` |
| `OPENROUTER_API_KEY` | texto / vazio | Chave Bearer exigida para ingestão e consulta |
| `EMBEDDING_MODEL` | texto / `qwen/qwen3-embedding-8b` | Modelo usado para vetorizar documentos e perguntas |
| `QUERY_INSTRUCTION` | texto / `Given a web search query, retrieve relevant passages that answer the query` | Instrução acrescentada apenas à pergunta; vazio a desativa |
| `REQUEST_TIMEOUT` | inteiro / `180` | Tempo máximo, em segundos, por chamada à OpenRouter; também usado no cliente do Qdrant servidor |
| `QDRANT_URL` | URL / vazio | Vazio seleciona Qdrant embutido; preenchido seleciona servidor |
| `QDRANT_API_KEY` | texto / vazio | Credencial opcional do Qdrant servidor |
| `QDRANT_PATH` | caminho / `data/qdrant` | Persistência do modo embutido; ignorado com `QDRANT_URL` |
| `QDRANT_COLLECTION` | texto / `smart_rag` | Nome da coleção vetorial |
| `TOP_K` | inteiro / `4` | Máximo de resultados pedidos ao Qdrant antes do limite de contexto |
| `SCORE_THRESHOLD` | número / `0.3` | Similaridade de cosseno mínima para aceitar um resultado |
| `MAX_CONTEXT_CHARS` | inteiro / `6000` | Limite de caracteres do contexto, inclusive cabeçalhos e separadores |
| `QDRANT_IMAGE` | texto / `qdrant/qdrant:latest` | Imagem do Qdrant usada somente pelo Compose |
| `QDRANT_PORT` | inteiro / `6333` | Porta do Qdrant publicada no host pelo Compose |
| `RAG_API_PORT` | inteiro / `8000` | Porta da API publicada no host pelo Compose |

Tamanho, lote, Top-K, orçamento e timeout devem ser positivos; `0 <= CHUNK_OVERLAP < CHUNK_SIZE` e o limiar deve estar entre -1 e 1. Caminhos relativos do `.env` são resolvidos a partir da raiz do projeto. A opção explícita `inspect --documents-dir` é relativa ao diretório de execução.

## Ingestão e consulta pela CLI

Coloque PDFs com texto extraível em `documents/` e execute:

```bash
python -m src.main inspect --pages-only
python -m src.main inspect --chunk-size 1000 --overlap 200
python -m src.main ingest
python -m src.main retrieve "Quais são os requisitos?"
python -m src.main retrieve "Quais são os requisitos?" --top-k 5 --score-threshold 0.4
```

`inspect` mostra páginas e amostras de chunks sem acessar OpenRouter nem abrir o banco. `ingest` indexa todos os PDFs e recusa substituir uma coleção existente. `retrieve` imprime JSON no mesmo formato da API. Código de saída: 0 para sucesso, inclusive sem resultados; 1 para erro tratado; 2 para argumentos inválidos.

| Opção da CLI | Efeito |
| --- | --- |
| `inspect --pages-only` | Mostra páginas sem gerar amostras de chunks |
| `inspect --documents-dir CAMINHO` | Substitui `DOCUMENTS_DIR` somente nesta inspeção |
| `inspect --chunk-size N` | Substitui `CHUNK_SIZE` somente nesta inspeção |
| `inspect --overlap N` | Substitui `CHUNK_OVERLAP` somente nesta inspeção |
| `ingest --rebuild` | Substitui a coleção inteira após preparar novos vetores |
| `retrieve --top-k N` | Substitui `TOP_K` para esta consulta |
| `retrieve --score-threshold N` | Substitui `SCORE_THRESHOLD` para esta consulta |

Para substituir o índice após mudar PDFs, fragmentação ou configuração de embeddings:

```bash
python -m src.main ingest --rebuild
```

A ingestão lê e vetoriza tudo antes de excluir o índice anterior; falhas nessas etapas o preservam. **A substituição não é transacional** depois da exclusão: uma falha ou interrupção pode deixar a coleção incompleta. Coordene rebuilds com as consultas. Alterar Top-K, limiar ou orçamento de contexto não exige reindexar. A assinatura identifica provedor, URL, modelo e instrução, mas não detecta mudanças internas de pesos sob o mesmo ID de modelo.

## API HTTP

Com Qdrant embutido, conclua a ingestão antes de iniciar a API e use apenas um processo para a mesma pasta do banco:

```bash
python -m uvicorn src.api:app --host 127.0.0.1 --port 8000 --workers 1
```

| Rota | Resultado |
| --- | --- |
| `POST /retrieve` | Recupera contexto e chunks com fontes |
| `GET /health` | `{"status":"ok"}`; verifica somente o processo |
| `GET /docs` / `GET /openapi.json` | Documentação interativa e esquema OpenAPI |

```bash
curl -X POST http://localhost:8000/retrieve \
  -H 'Content-Type: application/json' \
  -d '{"question":"Quais são os requisitos?","top_k":4,"score_threshold":0.3}'
```

| Campo de `POST /retrieve` | Tipo e regra | Efeito |
| --- | --- | --- |
| `question` | texto obrigatório; 1 a 10000 caracteres após remover espaços externos | Pergunta vetorizada para a busca |
| `top_k` | inteiro opcional de 1 a 100 | Substitui `TOP_K` nesta requisição |
| `score_threshold` | número opcional entre -1 e 1 | Substitui `SCORE_THRESHOLD` nesta requisição |

Omitir as opções ou enviar `null` usa os padrões. Campos extras, inclusive `model`, são rejeitados. Opções de uma requisição não alteram as seguintes.

Resposta ilustrativa:

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

Sem trechos adequados, retorna HTTP 200 com `{"context":"","chunks":[]}`. Pode retornar menos que Top-K por causa do limiar ou orçamento. A pontuação de similaridade não é probabilidade de correção.

| HTTP | Significado |
| --- | --- |
| 200 | Recuperação concluída, inclusive vazia |
| 400 | Valor ou configuração/índice incompatível |
| 409 | Índice inexistente |
| 422 | Corpo da requisição inválido |
| 502 | Falha de transporte ou resposta da OpenRouter |
| 503 | Chave ausente no servidor ou serviço indisponível |

Erros usam `{"detail": ...}`; validação 422 segue o formato do FastAPI. `/health` não testa índice, créditos ou OpenRouter. Não há endpoint de ingestão nem autenticação de consumidores: mantenha a API na rede interna do backend.

Exemplo de consumo em Node.js/TypeScript:

```typescript
const response = await fetch("http://localhost:8000/retrieve", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ question: "Quais são os requisitos?" }),
});
if (!response.ok) throw new Error(`RAG HTTP ${response.status}: ${await response.text()}`);
const { context, chunks } = await response.json();
// Use context no prompt do seu LLM e chunks para exibir as fontes.
```

## Uso em Python

Execute da raiz ou inclua a raiz no `PYTHONPATH`:

```python
from dataclasses import asdict
from src.rag import RAG

with RAG() as rag:
    result = rag.retrieve("Quais são os requisitos?", top_k=4)
    payload = asdict(result)
```

`RAG(settings)` aceita uma instância de `Settings`; sem argumento carrega `.env`. `RAG.ingest(rebuild=False)` retorna a quantidade de chunks. `retrieve()` retorna `RetrievalResponse(context, chunks)` e propaga exceções; `IndexNotReadyError` indica coleção ausente. Sem `with`, feche com `rag.close()`. Cada instância serializa operações com um lock; processos diferentes não compartilham esse lock.

## Qdrant e Docker Compose

Sem `QDRANT_URL`, o Qdrant embutido persiste em `data/qdrant/`. Com URL, usa um servidor; os índices dos dois modos são independentes. Para usar o servidor Docker a partir do Python no host, configure `QDRANT_URL=http://localhost:6333` e faça a ingestão nesse modo.

```bash
docker compose build app api
docker compose up -d qdrant
docker compose run --rm app ingest
docker compose up -d api
curl http://localhost:8000/health
docker compose run --rm app retrieve "Quais são os requisitos?"
docker compose down
```

O serviço `app` é uma CLI sob demanda; `api` usa um worker. Na rede do Compose, o backend chama `http://api:8000/retrieve`; no host, `http://localhost:8000/retrieve`. O Compose monta PDFs somente na CLI, publica portas em `127.0.0.1` e persiste dados nos volumes `qdrant_storage` e `qdrant_snapshots`. `docker compose down` preserva os volumes; `down -v` os remove. `depends_on` aguarda a inicialização do contêiner Qdrant, não sua prontidão.

## Testes e limites

```bash
python -m unittest discover -s tests -v
python -m pip check
docker compose config --quiet
```

Os testes usam PDFs temporários, Qdrant local e respostas simuladas da OpenRouter; não consomem créditos nem avaliam a qualidade do modelo. O projeto não oferece OCR, reranking, atualização incremental, histórico ou streaming. A ingestão mantém páginas, chunks e vetores em memória; tabelas e ordem de leitura dependem da extração do PDF. O limite em caracteres não garante que o contexto caiba na janela de tokens do LLM consumidor.

Textos dos documentos e perguntas são enviados à OpenRouter para embeddings. O contexto recuperado **não** é enviado por este serviço a um modelo de geração. Chaves, PDFs e dados locais devem permanecer fora do Git.
