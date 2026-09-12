# WADR

**WhatsApp Document Retrieval.** A personal search engine for the documents
that fly past you in chats: PDFs, Office files, photographed pages and voice
notes.

Files arrive through an adapter (a folder, or WhatsApp via the bridge). The
engine extracts text, dedupes by content hash, chunks and indexes it into
Postgres, and answers queries with a hybrid of BM25 and dense retrieval fused
by Reciprocal Rank Fusion. Boolean and TF-IDF models are implemented from
scratch alongside, as IR course lab evidence.

New teammate? Read this page, then open [TODO.md](TODO.md) and find your
workstream.

## Features

| Feature | What it does | How to use it |
|---|---|---|
| **Multi format ingest** | Extracts text from txt, md, pdf and docx, OCRs images with Tesseract, and transcribes voice notes with Whisper. | `uv run wadr ingest ./sample_docs` |
| **Content hash dedupe** | Identical bytes are stored once. Re-sharing a known file records another sighting instead of a second document. | Automatic on every ingest. |
| **Hybrid search** | BM25 and dense vectors ranked separately, then fused by RRF (k=60), with a recency boost. Catches both exact wording and paraphrases. | `uv run wadr search "tf-idf weighting"` |
| **Five retrieval models** | `hybrid`, `bm25`, `dense`, `tfidf`, `boolean`. The last two are the from scratch lab implementations with no retrieval libraries. | `uv run wadr search "biryani" --model bm25` |
| **Query filters** | Narrow by sender, chat, file type or date. Unknown prefixes stay in the query text. | `invoice from:dad in:family type:pdf after:2026-01-01` |
| **From scratch inverted index** | A hand built postings index next to the Postgres tsvector path, so the classical machinery is ours, not a library's. | `src/wadr/indexing/inverted_index.py` |
| **HTTP API** | Search, similar documents and feedback over JSON, which is what the bridge and any UI talk to. | `uv run uvicorn wadr.api.app:app` then `GET /search?q=exam+schedule` |
| **WhatsApp bridge** | Ingest by sending a file to a linked number, search with `/find`, fetch a result with `/get`. | See [docs/whatsapp-bridge.md](docs/whatsapp-bridge.md) |
| **Evaluation harness** | P@k, Recall, F1, MRR and nDCG computed by hand over judged queries, printed as a model by metric table for the report. | `uv run python -m wadr.evaluation.run_eval` |

## Setup

Prereqs: [Docker](https://docs.docker.com/get-docker/),
[uv](https://docs.astral.sh/uv/), and optionally [Ollama](https://ollama.com)
for dense and hybrid search (`ollama pull nomic-embed-text`). Without Ollama
everything still runs, with search degrading to BM25 only and a warning.

```sh
docker compose up -d      # Postgres 16 + pgvector
uv sync
uv run wadr migrate       # apply migrations/*.sql
```

Image OCR and voice notes need Tesseract and ffmpeg installed separately. Full
notes, including the Windows `PATH` trap, are in [docs/setup.md](docs/setup.md).

## Use

```sh
uv run wadr ingest ./sample_docs
uv run wadr search "tf-idf weighting"              # hybrid by default
uv run wadr search "biryani" --model bm25 --top-k 10
uv run uvicorn wadr.api.app:app                    # GET /search?q=exam+schedule
```

## Docs

| Document | Contents |
|---|---|
| [docs/setup.md](docs/setup.md) | Install, OCR and audio prerequisites, database |
| [docs/architecture.md](docs/architecture.md) | Layout, data flow, the two hard rules |
| [docs/retrieval.md](docs/retrieval.md) | The five models, filters, fusion, recency |
| [docs/whatsapp-bridge.md](docs/whatsapp-bridge.md) | Running the bridge, commands, why Baileys |
| [docs/evaluation.md](docs/evaluation.md) | Benchmark, judgments, metrics |
| [docs/configuration.md](docs/configuration.md) | Environment variables |
| [docs/schema.md](docs/schema.md) | Migrations and resets |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Branches, pull requests, hard rules |

## Tests and lint

```sh
uv run pytest          # skipped tests are the team checklist (test_todo_checklist.py)
uv run ruff check .
```
