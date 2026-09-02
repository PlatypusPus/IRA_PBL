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
npm run setup                  # bridge + web dependencies, builds the web app
```

## Run

```sh
npm start
```

That is both halves: the API and web app on :8000, the WhatsApp bridge on
:8085, with their output interleaved and prefixed. Ctrl-C stops both, and if
one dies the other is taken down with it - a half-running system that 500s
every upload is worse than a stopped one.

The two processes share a secret so nothing else can post documents into your
account. You do not have to invent or export one: the first `npm start` writes
a random `WADR_BRIDGE_TOKEN` to `.env` (gitignored) and both sides read it from
there, as does `uv run wadr ...`.

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

**Who sees what.** Your linked number sits in group chats full of other
people, and any of them can type `/find`. Only you - messages from your own
WhatsApp - search everything that number ever received. For anyone else the
search is narrowed to what they could already see: files shared in the chat
they are asking in, and files they sent themselves. `/get` re-checks the same
rule at send time, so a result nobody was allowed to find cannot be downloaded
either.

**A result marked "loose match" means nothing actually matched.** Semantic
search always returns its nearest neighbours, so rather than pretend, the app
shows them as guesses. Measured on this embedder a correct match can score
0.438 while pure noise scores 0.454 — the two genuinely overlap, so a score
threshold would throw away real answers. Labelling is honest where filtering
would be lossy.

## Give it to an agent (MCP)

WADR is an MCP server, so Claude — or any MCP client — can search and *read*
your documents and answer from their contents.

In the web app, click the plug icon next to your email, create a key, and paste
the config it shows you into Claude Desktop or Claude Code:

```json
{
  "mcpServers": {
    "wadr": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/IRPBL", "wadr", "mcp"],
      "env": { "WADR_API_KEY": "wadr_..." }
    }
  }
}
```

Or from the terminal: `uv run wadr apikey you@example.com`.

Four tools, deliberately few:

| tool | what it is for |
|---|---|
| `search_documents` | find candidates; supports the same `from:` / `type:` / `after:` filters |
| `read_document` | the extracted text, so the agent answers from contents rather than filenames |
| `recent_documents` | "what came in this week" |
| `find_similar` | "more like this one" |

A key is scoped to one account, so an agent can only ever reach documents that
account's own numbers received. Keys are stored as SHA-256 hashes — the
plaintext is shown once, at creation — and revoking one takes effect on the
next call. Search results carry `weak: true` when nothing really matched, and
the server's instructions tell the model to say so rather than bluff.

## The weekly digest

Documents arrive in group chats nobody reads to the end. `wadr digest` sends
each user a list of what actually landed on their numbers, to the number
itself, so the summary shows up in the same app the documents did:

```sh
uv run wadr digest --dry-run     # print it, send nothing
uv run wadr digest               # send
```

Schedule it weekly (cron, or Task Scheduler on Windows). Each digest starts
where the last one stopped rather than at "seven days ago", so a run that is
skipped - or a bridge that was offline for it - widens the next digest instead
of losing the week it missed.

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
| `WADR_API_KEY` | *(MCP server only — the agent's key)* |

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
