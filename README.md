# smart_rag

[English](readme.en.md)

Serviço de recuperação de documentos para um backend maior. Recebe uma pergunta,
busca trechos no Qdrant e devolve contexto com fontes. **Não gera respostas.**
O projeto consumidor escolhe seu LLM e usa os trechos para embasar a própria resposta.

## Arquitetura

```text
documents/*.pdf → pages → chunks → Qwen embeddings (OpenRouter) → Qdrant

Backend → question → POST /retrieve → question embedding → Qdrant Top-K
        ← context + chunks + metadata

Backend → its own LLM → final answer
```

- `src/api.py`: interface HTTP `POST /retrieve`.
- `src/rag.py`: interface Python `RAG.retrieve()` e `RAG.ingest()`.
- `src/main.py`: CLI `inspect`, `ingest` e `retrieve`.
- `src/llm_client.py`: transporte HTTP usado apenas pela API de embeddings.

O modelo configurado é `qwen/qwen3-embedding-8b`. Não há geração, chat,
`LLM_MODEL` ou endpoint `/ask`. Nenhuma chamada é feita a `/chat/completions`.

## Responsabilidades na aplicação maior

| Etapa | Este serviço | Backend consumidor |
| --- | --- | --- |
| Preparação | Extrai PDFs, divide em chunks e armazena embeddings no Qdrant | Disponibiliza os documentos e coordena a ingestão |
| Pergunta | Recebe a pergunta em `/retrieve` e gera seu embedding | Recebe a mensagem do usuário e resolve referências ao histórico |
| Recuperação | Busca trechos e retorna `context`, `chunks` e metadados | Seleciona como usar o contexto e trata resultados vazios |
| Geração | Retorna os dados recuperados | Envia pergunta e contexto ao próprio LLM antes de gerar a resposta |
| Entrega | Fornece PDF, página, texto e score dos trechos | Apresenta a resposta final e suas fontes ao usuário |

O RAG completo reúne recuperação e geração. Este repositório fornece a parte
de recuperação; o backend consumidor implementa a geração fundamentada nesses dados.

## Tecnologias utilizadas

### Linguagem e bibliotecas

| Tecnologia | Versão / origem | Uso no projeto |
| --- | --- | --- |
| Python | 3.12; validado com 3.12.14 | Implementação do pipeline e interfaces Python/HTTP |
| pypdf | 6.19.0 | Extração de texto e metadados por página de PDF |
| qdrant-client | 1.19.1 | Acesso ao Qdrant embutido ou servidor; gravação e busca de vetores |
| python-dotenv | 1.2.3 | Carregamento da configuração do `.env` |
| FastAPI | 0.141.1 | Endpoint `POST /retrieve`, validação HTTP e documentação OpenAPI |
| Uvicorn | 0.53.0 | Servidor ASGI que executa a API |
| Pydantic | Dependência transitiva do FastAPI/qdrant-client | Validação do corpo da requisição em `src/api.py` |
| Biblioteca padrão Python | Incluída no Python 3.12 | `dataclasses`, `pathlib`, `urllib.request`, `json`, `uuid`, `argparse` e sincronização |
| unittest / unittest.mock | Incluídos no Python 3.12 | Testes automatizados e simulação das respostas de embeddings |

As versões das dependências diretas estão fixadas em `requirements.txt`.
Dependências transitivas não são fixadas individualmente.

### Modelo, serviços e execução

| Tecnologia | Configuração atual | Uso no projeto |
| --- | --- | --- |
| Qwen3 Embedding 8B | `qwen/qwen3-embedding-8b` | Vetorização de documentos e perguntas |
| OpenRouter | `https://openrouter.ai/api/v1/embeddings` | Acesso remoto ao modelo de embeddings via HTTP com chave Bearer |
| Qdrant | Embutido ou imagem `qdrant/qdrant:latest` | Persistência de vetores/metadados e recuperação Top-K por similaridade de cosseno |
| Docker | Imagem base `python:3.12-slim` | Empacotamento da API e da CLI |
| Docker Compose | v2.24+ | Execução dos serviços `qdrant`, `api` e `app`, rede e volumes persistentes |
| HTTP / JSON / OpenAPI | `/retrieve`, `/docs` e `/openapi.json` | Contrato de integração com o backend consumidor |

Qdrant embutido usa a implementação do cliente Python; a versão da imagem do
servidor é independente de `qdrant-client`. `latest` e `3.12-slim` são tags
mutáveis. Docker é opcional para execução com Python e Qdrant embutido.
Node.js/TypeScript aparece como exemplo de consumo e não é uma dependência do serviço.

## Instalação

Requer Python 3.12 e chave OpenRouter com acesso ao modelo e créditos.
Embeddings precisam de acesso à rede. Docker/Compose v2.24+ é opcional.
Na raiz do repositório:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp -n .env.example .env
```

Se `.venv` já existir, apenas ative-a. `cp -n` preserva um `.env` existente.
Preencha a chave no `.env`; nunca a envie no corpo da requisição ao RAG.

```dotenv
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_API_KEY=your-key
EMBEDDING_MODEL=qwen/qwen3-embedding-8b
```

Dependências diretas: `pypdf==6.19.0`, `qdrant-client==1.19.1`,
`python-dotenv==1.2.3`, `fastapi==0.141.1`, `uvicorn==0.53.0`.
Sem LangChain, LlamaIndex ou SDK OpenRouter. Não há instalação via `pip install .`.

## Configuração

O `.env` é carregado da raiz; variáveis do ambiente prevalecem sobre ele.
Opções explícitas da CLI/HTTP/Python prevalecem sobre os respectivos padrões.
Caminhos relativos do `.env` são relativos à raiz; `inspect --documents-dir`
é relativo ao diretório atual.

| Variável | Padrão | Função |
| --- | --- | --- |
| `DOCUMENTS_DIR` | `documents` | Pasta dos PDFs |
| `CHUNK_SIZE` | `1000` | Caracteres por chunk |
| `CHUNK_OVERLAP` | `200` | Sobreposição em caracteres |
| `BATCH_SIZE` | `16` | Textos por chamada de embeddings |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | URL base |
| `OPENROUTER_API_KEY` | `—` | Chave Bearer; padrão vazio |
| `EMBEDDING_MODEL` | `qwen/qwen3-embedding-8b` | Modelo de embeddings |
| `QUERY_INSTRUCTION` | `Given a web search query, retrieve relevant passages that answer the query` | Prefixo da consulta; vazio desativa |
| `REQUEST_TIMEOUT` | `180` | Timeout em segundos por chamada |
| `QDRANT_URL` | `—` | Vazio: embutido; preenchido: servidor |
| `QDRANT_API_KEY` | `—` | Chave do Qdrant; padrão vazio |
| `QDRANT_PATH` | `data/qdrant` | Pasta do banco embutido |
| `QDRANT_COLLECTION` | `smart_rag` | Coleção do índice |
| `TOP_K` | `4` | Máximo de hits antes do orçamento de contexto |
| `SCORE_THRESHOLD` | `0.3` | Similaridade mínima de cosseno |
| `MAX_CONTEXT_CHARS` | `6000` | Orçamento incluindo cabeçalhos |
| `QDRANT_IMAGE` | `qdrant/qdrant:latest` | Imagem Compose |
| `QDRANT_PORT` | `6333` | Porta Qdrant no host (Compose) |
| `RAG_API_PORT` | `8000` | Porta do RAG no host (Compose) |

Tamanho, lote, Top-K, orçamento e timeout devem ser positivos.
`0 <= CHUNK_OVERLAP < CHUNK_SIZE`; limiar entre -1 e 1.
`inspect` funciona sem chave e sem abrir o banco.

## Ingestão e CLI

Coloque os PDFs em `documents/` e execute na raiz:

```bash
python -m src.main inspect --pages-only
python -m src.main inspect --chunk-size 1000 --overlap 200
python -m src.main inspect --documents-dir ./documents
python -m src.main ingest
python -m src.main retrieve "Quais são os requisitos?"
python -m src.main retrieve "Quais são os requisitos?" --top-k 5 --score-threshold 0.4
python -m src.main --help
```

`inspect` imprime amostras. `ingest` indexa todos os PDFs e recusa uma coleção
existente. `retrieve` imprime JSON com o mesmo formato da API. Código de saída:
0 para sucesso (inclusive nenhum resultado), 1 para erros tratados, 2 para
argumentos inválidos. Não existe mais o comando `ask`.

## API HTTP

Com Qdrant embutido, conclua a ingestão antes de iniciar a API.
Use um único worker e pare a API antes de outra ingestão pela CLI.

```bash
python -m uvicorn src.api:app --host 127.0.0.1 --port 8000 --workers 1
```

| Rota | Função |
| --- | --- |
| `POST /retrieve` | Recupera trechos e contexto |
| `GET /health` | Retorna `{"status":"ok"}`; somente processo ativo |
| `GET /docs` | Documentação interativa |
| `GET /openapi.json` | Esquema OpenAPI |

Basta enviar a pergunta:

```bash
curl -X POST http://localhost:8000/retrieve \
  -H 'Content-Type: application/json' \
  -d '{"question":"Quais são os requisitos?"}'
```

| Campo | Regra |
| --- | --- |
| `question` | Obrigatório; 1–10000 caracteres após remover espaços externos |
| `top_k` | Opcional; inteiro de 1 a 100, padrão `TOP_K` |
| `score_threshold` | Opcional; número entre -1 e 1, padrão `SCORE_THRESHOLD` |

Omitir ou enviar null nas opções usa os padrões. Campos extras, incluindo
`model`, são rejeitados. Cada requisição mantém a configuração global intacta.
Formato de resposta; texto e score abaixo são ilustrativos:

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

`context` concatena os trechos com cabeçalhos. `chunks` contém exatamente os
mesmos trechos, em forma estruturada; `reference` corresponde a `[1]`, `[2]`, etc.
A resposta pode conter menos de Top-K: o limiar e o orçamento de contexto
eliminam trechos. Somente chunks completos que cabem no orçamento são retornados;
se um não couber, um trecho menor posterior ainda pode entrar.
Sem resultados, retorna HTTP 200 com `{"context":"","chunks":[]}`.
Não há resposta gerada nem mensagem de abstenção.

| HTTP | Significado |
| --- | --- |
| 200 | Recuperação concluída, inclusive sem resultados |
| 400 | Configuração/índice incompatível ou valor inválido no pipeline |
| 409 | Índice inexistente |
| 422 | Requisição inválida |
| 502 | Falha de transporte/resposta do provedor de embeddings |
| 503 | Chave ausente no servidor ou serviço indisponível |

Erros usam `{"detail": ...}`; validação 422 retorna lista de erros FastAPI.
`/health` não verifica índice, créditos ou OpenRouter. Não há endpoint de ingestão
nem autenticação de consumidores. Mantenha o serviço na rede interna do backend.

## Consumo pelo backend

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

O backend usa `context` no prompt do próprio LLM, ou monta seu contexto a partir
de `chunks`. Ele também controla histórico, idioma, modelo, resposta final e
exibição das fontes. Os documentos recuperados são dados, não instruções a executar.

## Consumo em Python

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

Execute da raiz ou inclua-a no `PYTHONPATH`. `RAG(settings)` aceita `Settings`;
sem argumento carrega `.env`. `retrieve()` aceita `top_k` e `score_threshold`
opcionais e retorna `RetrievalResponse`. `ingest()` retorna a quantidade de chunks.
Sem `with`, feche com `rag.close()`. Exceções são propagadas;
`IndexNotReadyError` indica índice ausente.

Cada instância serializa suas operações com um lock. A API mantém uma instância
e a fecha ao parar. O banco embutido permite um processo por pasta. Para múltiplos
processos use Qdrant servidor; o lock não coordena instâncias diferentes.

## Componentes e contratos

| Arquivo | Função |
| --- | --- |
| `src/config.py` | Configuração e validação |
| `src/pdf_loader.py` | PDF → DocumentPage |
| `src/chunker.py` | Páginas → DocumentChunk |
| `src/llm_client.py` | HTTP JSON autenticado para embeddings |
| `src/embeddings.py` | Vetores dos textos e perguntas |
| `src/vector_store.py` | Persistência, assinatura e busca cosseno |
| `src/ingest.py` | Coordenação da ingestão |
| `src/retriever.py` | Top-K e montagem de contexto |
| `src/rag.py` | Interface Python pública |
| `src/api.py` | Interface HTTP pública |
| `src/main.py` | CLI |

```text
DocumentPage: source, page_number, text
DocumentChunk: source, page_number, chunk_index, text
SearchHit: chunk, score
Context: text, sources
RetrievedChunk: reference, source, page_number, chunk_index, score, text
RetrievalResponse: context, chunks
```

PDFs são lidos por nome, somente `*.pdf` diretamente na pasta. Páginas começam
em 1; páginas vazias são ignoradas sem renumerar as seguintes. `source` inclui
a extensão. Pasta inválida/PDF ilegível gera erro. Não há OCR.

Chunks não cruzam páginas; `chunk_index` começa em 0 por página. As janelas
avançam `chunk_size - overlap` caracteres Unicode (não tokens), podem cortar
palavras e ignoram janelas só de espaços. A última pode ser menor.

Embeddings usam `POST /embeddings`, Bearer e `encoding_format=float`.
A resposta é ordenada por `data[].index`. Quantidade, índices, dimensões,
valores finitos e vetores não nulos são validados. Documentos não recebem prefixo;
perguntas usam `Instruct: {QUERY_INSTRUCTION}\nQuery: {question}`.

Qdrant usa dimensão detectada, distância cosseno e IDs UUID5 da serialização
estável dos campos do chunk. O payload guarda esses campos e a assinatura de
provedor/URL/modelo/instrução. A busca verifica assinatura e dimensão.

## Reconstrução

```bash
python -m src.main ingest --rebuild
```

Reconstrua após mudanças nos PDFs, chunking ou configuração de embeddings.
Mudar Top-K, limiar ou orçamento não exige reconstrução. Mudanças nos pesos ou
roteamento sob o mesmo ID de modelo não são detectadas pela assinatura.

Leitura e embeddings são concluídos antes de apagar o índice anterior. Falhas
nessas etapas ou falta de texto o preservam. A substituição **não é transacional**:
após exclusão não há rollback. Falhas na escrita tentam excluir a coleção parcial;
interrupções abruptas podem deixá-la incompleta. Coordene reconstruções para não
coincidirem com consultas e use uma coleção dedicada.

## Docker e Qdrant

```bash
docker compose build app api
docker compose up -d qdrant
docker compose run --rm app ingest
docker compose up -d api
curl http://localhost:8000/health
docker compose run --rm app retrieve "Quais são os requisitos?"
docker compose down
```

O serviço `api` executa Uvicorn com um worker. `app` usa o perfil `cli` e roda
sob demanda. Um backend na mesma rede Docker usa `http://api:8000/retrieve`;
no host usa `http://localhost:8000/retrieve`. Ajuste a porta com `RAG_API_PORT`.
A porta 6333 é do banco, não do serviço de recuperação.

O Compose repassa `.env` e fixa `DOCUMENTS_DIR=/app/documents`,
`QDRANT_URL=http://qdrant:6333` e `QDRANT_API_KEY` vazia. A CLI monta os PDFs
somente para leitura; a API não precisa dessa pasta. Portas são publicadas em
127.0.0.1. O Qdrant do Compose não configura autenticação. Seu `depends_on`
verifica início, não prontidão: consulte os logs e repita se ainda estiver iniciando.

Volumes `qdrant_storage` e `qdrant_snapshots` persistem após `down`;
`down -v` apaga os dados. O Dockerfile usa usuário não root e Python 3.12 slim.
`.env`, `.venv`, PDFs, testes e bancos não entram na imagem. Reconstrua a imagem
ao atualizar código/dependências. Tags são mutáveis; fixe digests para reprodução
exata. Dependências transitivas não têm lockfile.

Sem `QDRANT_URL`, o Python usa banco embutido em `data/qdrant`. Para usar o
servidor Docker a partir do host, configure o trecho abaixo. Modos embutido e
servidor não compartilham índices; faça ingestão no modo escolhido.

```dotenv
QDRANT_URL=http://localhost:6333
```

Se mudar `QDRANT_PORT`, ajuste essa URL no host. A URL interna não muda.

## Testes e diagnóstico

```bash
python -m unittest discover -s tests -v
python -m pip check
docker compose config --quiet
```

Testes usam PDFs temporários, Qdrant real local e embeddings simulados. Cobrem
extração, chunks, ranking, persistência, reconstrução, assinatura, orçamento,
autenticação, contrato HTTP, resultados vazios e fechamento do banco. Verificam
que as chamadas são somente de embeddings. Não avaliam qualidade do modelo nem
consomem créditos. Python usado na validação: 3.12.14.

- Chave ausente: preencha `OPENROUTER_API_KEY`.
- Erros OpenRouter 401/403: chave/acesso; 402: créditos; 429: aguarde e reduza chamadas.
  Na API HTTP de recuperação, erros de provedor são apresentados como 502.
- Não há retry automático; timeout usa `REQUEST_TIMEOUT`.
- Índice incompatível/existente: use `ingest --rebuild` quando quiser substituí-lo.
- Nenhum texto: confira pasta, extensão e se o PDF possui texto extraível.
- Nenhum trecho: confira limiar, documentos e `MAX_CONTEXT_CHARS`.
- Banco embutido bloqueado: feche o outro processo ou use servidor.
- Docker sem permissão: confira acesso do usuário ao daemon.

## Limites e migração

O consumidor deve migrar de `/ask` para `/retrieve`, de `RAG.ask()` para
`RAG.retrieve()` e de resposta gerada para `context`/`chunks`. Não envie `model`.
Atualizar o código de recuperação não exige reindexar se os embeddings não mudaram.

Não há OCR, reranker, ingestão incremental, histórico ou streaming. Páginas,
chunks e vetores são mantidos em memória durante ingestão. Similaridade não é
probabilidade de acerto. A ordem de leitura e tabelas dependem do PDF.
O orçamento em caracteres não garante encaixe na janela do LLM do consumidor.

Documentos e perguntas são enviados à OpenRouter para embeddings. Nenhum LLM
de geração recebe o contexto por este serviço. Chaves, PDFs e dados locais
são excluídos do Git; a chave não deve ser versionada.

Para equivalência em TypeScript, preserve metadados, numeração, prefixo da
consulta, cosseno e recorte Unicode com `Array.from(text)`. Se compartilhar IDs,
reproduza a serialização usada pelo UUID5.
# smart_rag
