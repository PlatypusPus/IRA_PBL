# WADR

Search every document you have ever been sent on WhatsApp.

WADR links your WhatsApp numbers, reads everything shared with them (including
text inside photographed pages and words spoken in voice notes), and lets you
find any of it by asking for it, from the web app or from WhatsApp itself.

> This is the **product** branch. `main` is the IR coursework version with
> hand written Boolean, TF-IDF and inverted index implementations plus a
> relevance judging harness. None of that is here. This branch keeps only what
> helps someone find a document and uses mature libraries (`rank_bm25`,
> `nomic-embed-text`, `faster-whisper`, Tesseract).

## Features

| Feature | What it does | How to use it |
|---|---|---|
| **Automatic ingest** | Every document, image and voice note sent to a linked number is extracted, chunked and indexed within seconds. Identical files are stored once, by SHA-256. | Link a number and it starts on its own. Nothing to upload. |
| **Reads scans and voice notes** | Tesseract OCRs photographed pages, faster-whisper transcribes audio, so a scanned fee receipt is searchable by its contents. | Needs Tesseract and ffmpeg installed. See [docs/setup.md](docs/setup.md). |
| **Hybrid search** | BM25 keywords and dense vectors, fused by Reciprocal Rank Fusion and nudged by recency, so both exact words and paraphrases work. | Type what you want in the web app search box. |
| **Filters** | Narrow by sender, chat, file type or date. | `invoice from:dad`, `notes in:family`, `receipt type:pdf`, `timetable after:2026-01-01` |
| **Search from WhatsApp** | Find and fetch documents without opening the web app. | `/find <query>` for a ranked list, `/get <n>` to have the file sent back. |
| **Per user visibility** | A document is yours because one of your numbers received it. In group chats, other people only ever see what they could already see. | Automatic. Details in [docs/architecture.md](docs/architecture.md). |
| **One line summaries** | Every result carries a readable summary, which is the only useful thing to show when WhatsApp named the file `1787227836920-lnml9ufa.pdf`. | Set `WADR_SUMMARY_MODEL`, then `uv run wadr summarize`. See [docs/digest.md](docs/digest.md). |
| **Weekly digest** | A list of what actually landed on your numbers, sent to the number itself. A skipped run widens the next digest instead of losing the week. | `uv run wadr digest --dry-run`, then schedule `uv run wadr digest`. |
| **MCP server** | Claude or any MCP client can search and read your documents and answer from their contents. | Create a key with the plug icon in the web app. See [docs/mcp.md](docs/mcp.md). |
| **Honest results** | When nothing really matched, results are labelled "loose match" rather than presented as answers. | Nothing to configure. Reasoning in [docs/architecture.md](docs/architecture.md). |

## Quick start

Prereqs: [Docker](https://docs.docker.com/get-docker/),
[uv](https://docs.astral.sh/uv/), [Node 18+](https://nodejs.org), and
[Ollama](https://ollama.com) for semantic search (`ollama pull nomic-embed-text`).
Scans and voice notes also need Tesseract and ffmpeg.

```sh
docker compose up -d     # Postgres 16 + pgvector
uv sync
uv run wadr migrate      # apply migrations/*.sql
npm run setup            # bridge + web dependencies, builds the web app
npm start                # API and web on :8000, WhatsApp bridge on :8085
```

Open <http://localhost:8000>, create an account, then **+** in the sidebar to
link a number. Scan the QR from **Settings > Linked devices > Link a device**,
or use the pairing code, which is usually faster on iPhone.

Full install notes, including Windows and optional extras, are in
[docs/setup.md](docs/setup.md).

## Usage

Ask for what you want in the web app, optionally with filters:

```
invoice from:dad
notes in:family
receipt type:pdf
timetable after:2026-01-01
```

Or from any WhatsApp chat your linked number is in:

```
/find exam timetable
/get 2
```

## Docs

| Document | Contents |
|---|---|
| [docs/setup.md](docs/setup.md) | Install, run, passwords, UI development |
| [docs/architecture.md](docs/architecture.md) | How it fits together, tenancy, ranking, honest results |
| [docs/mcp.md](docs/mcp.md) | Giving an agent access, tools, key scope |
| [docs/digest.md](docs/digest.md) | Weekly digest and document summaries |
| [docs/configuration.md](docs/configuration.md) | Environment variables |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Branches, pull requests, hard rules |

## Tests and lint

```sh
uv run pytest        # includes tenancy tests: accounts must not see each other
uv run ruff check .
cd web && npm run build
```
