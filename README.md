# WADR — WhatsApp Document Retrieval

WADR is a personal search engine for the documents that fly past you on
WhatsApp — PDFs, images, voice notes shared in chats. A thin adapter layer
captures files from a channel (terminal today; WhatsApp via Baileys in WS1),
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
| WhatsApp bridge  |    |                |
| (Baileys, Node)  |    |   CLIAdapter   |          adapters/ -- THIN,
+--------+---------+    |   (working)    |          no IR logic inside
         | webhook      +-------+--------+
         v                      |
+------------------+            |
|  OpenWAAdapter   |            |
|  (working)       |            |
+--------+---------+            |
         |    on_document()     |
         v                      v
+---------------------------------------------------+
| ingestion/   router -> extractor -> dedupe(SHA256) |
|              -> chunker                            |
|              txt/md/pdf/docx/image-OCR/voice-ASR   |
+-------------------------+-------------------------+
                          v
+---------------------------------------------------+
| indexing/    embedder (Ollama, optional)           |     PostgreSQL 16
|              lexical (tsvector)              ----> |     + pgvector
|              inverted_index (from scratch)         |
+-------------------------+-------------------------+
                          v
+---------------------------------------------------+
| retrieval/   bm25 | dense | tfidf | boolean        |
|                   \     /                          |
|                RRF fusion (k=60)                   |
|              filters, recency boost                |
+-------------------------+-------------------------+
                          v
              results -> adapter.send_results()

| evaluation/  P@k Recall F1 MRR nDCG -- by hand      |
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

Image OCR needs the Tesseract executable on the system — `pytesseract` only
wraps it, so pip-installing the Python package alone is not enough:

```sh
brew install tesseract          # macOS; Linux: apt install tesseract-ocr
winget install UB-Mannheim.TesseractOCR   # Windows
```

On Windows the installer does not add Tesseract to `PATH`. Either add
`C:\Program Files\Tesseract-OCR` to it, or set `pytesseract.pytesseract.tesseract_cmd`
to the full `tesseract.exe` path — otherwise `pytesseract` raises
`TesseractNotFoundError` and every image is skipped.

Voice-note transcription needs `ffmpeg`, plus a one-time download of the
Whisper `base` model (~150 MB, cached under `~/.cache/huggingface`):

```sh
brew install ffmpeg             # macOS; Linux: apt install ffmpeg
```

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

Models: `hybrid` (default) | `bm25` | `dense` | `tfidf` | `boolean`.
`tfidf` and `boolean` are the from-scratch course-lab implementations —
no retrieval libraries, see their module docstrings.

## WhatsApp bridge

Needs [Node 18+](https://nodejs.org). The bridge owns the WhatsApp session and
forwards documents / `/find` queries to the API (contract in
`src/wadr/adapters/openwa.py`). Internally it uses
[Baileys](https://github.com/WhiskeySockets/Baileys) — no browser. Both open-wa
and whatsapp-web.js were tried and both broke on media download against current
WhatsApp Web (they drive a real browser page and call WhatsApp internals that
keep changing); Baileys speaks the protocol directly and decrypts media itself.
Route and adapter names keep `openwa` from the original assignment; the bridge
library sits behind an unchanged HTTP contract.

```sh
uv run uvicorn wadr.api.app:app        # terminal 1: the WADR API
cd bridge && npm install && npm start  # terminal 2: the bridge
```

The bridge reads an optional `.env` at the repo root (Node's native
`--env-file-if-exists`, no dotenv dependency) — e.g. `WADR_API=http://localhost:8017`
if port 8000 is busy on your machine (then run uvicorn with `--port 8017`).

Then open <http://localhost:8085> and scan the QR with WhatsApp
(**Linked devices → Link a device**). Once connected:

- **Send any PDF/document** to ingest it — the bridge reacts ✅ (saved), 📎
  (already had it), or ❌ (failed), so the sender isn't left guessing.
- **`/find <query>`** searches and replies with a ranked list.
- **`/get <n>`** sends back the nth file from your last `/find`.

Re-forwarding a known file records a sighting, not a new document. Files
ingested before the `content` column (migration 0002) can't be `/get`-ed until
re-shared.

## Tests & lint

```sh
uv run pytest          # skipped tests are the team checklist (test_todo_checklist.py)
uv run ruff check .
```

## Benchmark

```sh
uv run python -m wadr.evaluation.run_eval    # model x metric table for the report
```

Judgments live in `evaluation/queries.jsonl` (format in
`src/wadr/evaluation/judgments.py`), keyed by `file_hash` so they survive a DB
wipe and re-ingest. Metrics are hand-implemented in `evaluation/metrics.py` —
no sklearn, no pytrec_eval.

## Configuration

| Env var                  | Default                                      |
|--------------------------|----------------------------------------------|
| `WADR_DATABASE_URL`      | `postgresql://wadr:wadr@localhost:5433/wadr` |
| `WADR_OLLAMA_URL`        | `http://127.0.0.1:11434`                     |
| `WADR_OPENWA_BRIDGE_URL` | `http://127.0.0.1:8085` (WS1)                |

The two HTTP defaults are `127.0.0.1`, not `localhost`, on purpose: `localhost`
resolves to `::1` first, both services bind IPv4, and Python's urllib has no
Happy Eyeballs fallback — it stalls ~2s per call before retrying IPv4. Keep the
literal IP if you override them on a single machine.

## Schema changes

The schema lives in `migrations/` as numbered plain-SQL files, tracked in the
`schema_migrations` table. To change the schema: add
`migrations/000N_<what-it-does>.sql` (never edit a file that has already been
applied), then `uv run wadr migrate`. Full reset (drops data):
`docker compose down -v && docker compose up -d && uv run wadr migrate`.
