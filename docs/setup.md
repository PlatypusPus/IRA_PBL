# Setup

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) for Postgres 16 with pgvector
- [uv](https://docs.astral.sh/uv/) for the Python side
- [Node 18+](https://nodejs.org) for the bridge and the web app
- [Ollama](https://ollama.com) for semantic search (`ollama pull nomic-embed-text`)

Without Ollama everything still runs, but search falls back to keywords only.

Scanned images need Tesseract and voice notes need ffmpeg:

```sh
brew install tesseract ffmpeg            # macOS
sudo apt install tesseract-ocr ffmpeg    # Linux
winget install UB-Mannheim.TesseractOCR  # Windows (install ffmpeg too)
```

On Windows the Tesseract installer does not touch `PATH`. Add
`C:\Program Files\Tesseract-OCR` yourself, or image OCR silently skips files.

## Install

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
one dies the other is taken down with it. A half running system that 500s every
upload is worse than a stopped one.

The two processes share a secret so nothing else can post documents into your
account. You do not have to invent or export one: the first `npm start` writes
a random `WADR_BRIDGE_TOKEN` to `.env` (gitignored) and both sides read it from
there, as does `uv run wadr ...`.

## Linking a number

Open <http://localhost:8000>, create an account, then **+** in the sidebar to
link a number. Scan the QR from **Settings > Linked devices > Link a device**,
or use the pairing code. iPhone cameras read on screen QRs poorly, so the code
is usually faster there.

## Passwords

Passwords are stored as salted scrypt hashes, so a forgotten one cannot be
looked up, only replaced. Nothing sends email, so this is done from the
terminal by whoever runs the database:

```sh
uv run wadr passwd                     # list the accounts that exist
uv run wadr passwd you@example.com     # set a new password
```

## UI development

```sh
cd web && npm run dev
```

Hot reload on :5173, with `/api` proxied to :8000.
