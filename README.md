# WADR — WhatsApp Document Retrieval

WADR is a personal search engine for the documents that fly past you on
WhatsApp — PDFs, images, voice notes shared in chats. A thin adapter layer
captures files from a channel (terminal today; WhatsApp via open-wa in WS1),
the engine extracts text, dedupes by content hash, chunks and indexes it into
Postgres (tsvector + pgvector embeddings), and answers queries with a hybrid
of BM25 and dense retrieval fused by Reciprocal Rank Fusion — with
from-scratch Boolean and TF-IDF models alongside as IR course lab evidence.
New teammate? Read this page, then open [TODO.md](TODO.md) and find your
workstream.

## Architecture

```
 WhatsApp chats            ./sample_docs (or any folder)
      |                          |
      v                          v
+------------------+    +----------------+
| open-wa bridge   |    |                |
| (Node, TODO WS1) |    |   CLIAdapter   |          adapters/ -- THIN,
+--------+---------+    |   (working)    |          no IR logic inside
         | webhook      +-------+--------+
         v                      |
+------------------+            |
|  OpenWAAdapter   |            |
|  (skeleton, WS1) |            |
+--------+---------+            |
         |    on_document()     |
         v                      v
+---------------------------------------------------+
| ingestion/   router -> extractor -> dedupe(SHA256) |
|              -> chunker                            |
|              txt/pdf work; docx/ocr/asr = WS2      |
+-------------------------+-------------------------+
                          v
+---------------------------------------------------+
| indexing/    embedder (Ollama, optional)           |     PostgreSQL 16
|              lexical (tsvector)              ----> |     + pgvector
|              inverted_index (stub, SHARED)         |
+-------------------------+-------------------------+
                          v
+---------------------------------------------------+
| retrieval/   bm25 | dense | tfidf* | boolean*      |
|                   \     /                          |
|                RRF fusion (k=60)                   |
|              filters*, recency boost*   (*=stub)   |
+-------------------------+-------------------------+
                          v
              results -> adapter.send_results()

| evaluation/  P@k Recall F1 MRR nDCG -- by hand, WS3 |
```

Two hard rules, enforced in review (details in
[CONTRIBUTING.md](CONTRIBUTING.md)):

1. **The engine never imports adapters.**
2. **Classical IR modules stay library-free.**

## Setup

Prereqs: [Docker](https://docs.docker.com/get-docker/),
[uv](https://docs.astral.sh/uv/), and optionally [Ollama](https://ollama.com)
for dense/hybrid search (`ollama pull nomic-embed-text`). Without Ollama
everything still runs — search degrades to BM25-only with a warning.

```sh
docker compose up -d      # Postgres 16 + pgvector
uv sync
uv run wadr migrate       # apply schema migrations (migrations/*.sql)
```

## Use

```sh
uv run wadr ingest ./sample_docs
uv run wadr search "tf-idf weighting" --model hybrid
uv run wadr search "biryani" --model bm25
uv run uvicorn wadr.api.app:app     # then GET http://localhost:8000/search?q=exam+schedule
```

Models: `hybrid` (default) | `bm25` | `dense` | `tfidf`* | `boolean`*
(* = stub, see [TODO.md](TODO.md)).

## Tests & lint

```sh
uv run pytest          # skipped tests are the team checklist (test_todo_checklist.py)
uv run ruff check .
```

## Configuration

| Env var                  | Default                                      |
|--------------------------|----------------------------------------------|
| `WADR_DATABASE_URL`      | `postgresql://wadr:wadr@localhost:5433/wadr` |
| `WADR_OLLAMA_URL`        | `http://localhost:11434`                     |
| `WADR_OPENWA_BRIDGE_URL` | `http://localhost:8085` (WS1)                |

## Schema changes

The schema lives in `migrations/` as numbered plain-SQL files, tracked in the
`schema_migrations` table. To change the schema: add
`migrations/000N_<what-it-does>.sql` (never edit a file that has already been
applied), then `uv run wadr migrate`. Full reset (drops data):
`docker compose down -v && docker compose up -d && uv run wadr migrate`.
