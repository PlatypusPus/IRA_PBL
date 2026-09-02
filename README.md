# WADR — search your WhatsApp documents

Every useful PDF, scan, and voice note you have ever been sent is buried in a
chat somewhere. WADR links your WhatsApp numbers, reads everything shared with
them — including text inside photographed pages and words spoken in voice notes
— and lets you find any of it by asking for it.

Sign up, link one or more numbers, then search from the web app or from
WhatsApp itself with `/find`.

> This is the **product** branch. `main` is the IR coursework version:
> hand-written Boolean / TF-IDF / inverted-index implementations and a
> relevance-judging benchmark harness. None of that is here — this branch keeps
> only what helps someone find a document, and uses mature libraries
> (`rank_bm25`, `nomic-embed-text`, `faster-whisper`, Tesseract) instead of
> teaching implementations.

## How it works

```
   your WhatsApp numbers                    browser
        |  (Baileys)                           |
        v                                      v
 +------------------+              +------------------------+
 |  bridge/ (Node)  |  webhooks    |  web/ (React, shadcn)  |
 |  N sessions,     |------------->|  chat UI + linking     |
 |  one per number  |              +-----------+------------+
 +------------------+                          | /api
        |                                      v
        |                        +-----------------------------+
        +----------------------->|  FastAPI (wadr.api.app)     |
                                 +--------------+--------------+
                                                v
        ingest: extract -> dedupe (SHA-256) -> chunk -> embed
        search: BM25 + dense vectors, fused by RRF, recency-nudged
                                                v
                                   PostgreSQL 16 + pgvector
```

**Tenancy.** Identical bytes are stored once, but *visibility* is per sighting:
a document is yours because one of **your** numbers received it. Search,
download, and more-like-this are all scoped in `retrieval/service.py`, in one
place, so no caller can forget to.

## Setup

Prereqs: [Docker](https://docs.docker.com/get-docker/),
[uv](https://docs.astral.sh/uv/), [Node 18+](https://nodejs.org), and
[Ollama](https://ollama.com) for semantic search (`ollama pull nomic-embed-text`).
Without Ollama everything still runs — search falls back to keywords only.

Scanned images need Tesseract, and voice notes need ffmpeg:

```sh
brew install tesseract ffmpeg            # macOS
sudo apt install tesseract-ocr ffmpeg    # Linux
winget install UB-Mannheim.TesseractOCR  # Windows (install ffmpeg too)
```

On Windows the Tesseract installer does not touch `PATH` — add
`C:\Program Files\Tesseract-OCR` yourself, or image OCR silently skips files.

```sh
docker compose up -d           # Postgres 16 + pgvector
uv sync
uv run wadr migrate            # apply migrations/*.sql
cd web && npm install && npm run build && cd ..
```

## Run

The bridge and the API share a secret so nothing else can post documents into
your account. Pick any random string and set it for both:

```sh
export WADR_BRIDGE_TOKEN="$(openssl rand -hex 16)"

uv run uvicorn wadr.api.app:app        # terminal 1 — API + web app on :8000
cd bridge && npm start                 # terminal 2 — WhatsApp sessions on :8085
```

Open <http://localhost:8000>, create an account, then **+** in the sidebar to
link a number. Scan the QR from **Settings → Linked devices → Link a device**,
or use the pairing code — iPhone cameras read on-screen QRs poorly, so the code
is usually faster there.

For UI work, `cd web && npm run dev` gives hot reload on :5173 and proxies
`/api` to :8000.

## Using it

In the web app, ask for what you want. Filters narrow the search:

| token | example |
|---|---|
| `from:` | `invoice from:dad` |
| `in:` | `notes in:family` |
| `type:` | `receipt type:pdf` |
| `before:` / `after:` | `timetable after:2026-01-01` |

From WhatsApp itself: `/find <query>` replies with a ranked list, and
`/get <n>` sends the file back.

**A result marked "loose match" means nothing actually matched.** Semantic
search always returns its nearest neighbours, so rather than pretend, the app
shows them as guesses. Measured on this embedder a correct match can score
0.438 while pure noise scores 0.454 — the two genuinely overlap, so a score
threshold would throw away real answers. Labelling is honest where filtering
would be lossy.

## Tests & lint

```sh
uv run pytest        # includes tenancy tests: accounts must not see each other
uv run ruff check .
cd web && npm run build
```

## Configuration

| Env var | Default |
|---|---|
| `WADR_DATABASE_URL` | `postgresql://wadr:wadr@localhost:5433/wadr` |
| `WADR_OLLAMA_URL` | `http://127.0.0.1:11434` |
| `WADR_EMBED_MODEL` | `nomic-embed-text` |
| `WADR_BRIDGE_URL` | `http://127.0.0.1:8085` |
| `WADR_BRIDGE_TOKEN` | *(required — same value in both processes)* |

The HTTP defaults are `127.0.0.1`, not `localhost`, deliberately: `localhost`
resolves to `::1` first, these services bind IPv4, and Python's urllib has no
Happy Eyeballs fallback — it stalls ~2s per call before retrying IPv4.

If `ollama pull` leaves you with a tagged model (`nomic-embed-text:v1.5`)
instead of `:latest`, either `ollama cp` it or set `WADR_EMBED_MODEL`. The
embedder says which it is rather than claiming Ollama is down.

## Schema changes

Numbered plain-SQL files in `migrations/`, tracked in `schema_migrations`. Add
`migrations/000N_<what-it-does>.sql` (never edit an applied file), then
`uv run wadr migrate`. Full reset (drops data):
`docker compose down -v && docker compose up -d && uv run wadr migrate`.
