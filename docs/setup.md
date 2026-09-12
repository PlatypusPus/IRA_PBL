# Setup

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) for Postgres 16 with pgvector
- [uv](https://docs.astral.sh/uv/) for the Python side
- [Ollama](https://ollama.com), optional, for dense and hybrid search
  (`ollama pull nomic-embed-text`)

Without Ollama everything still runs. Search degrades to BM25 only, with a
warning.

## Image OCR

OCR needs the Tesseract executable on the system. `pytesseract` only wraps it,
so pip installing the Python package alone is not enough:

```sh
brew install tesseract                    # macOS
sudo apt install tesseract-ocr            # Linux
winget install UB-Mannheim.TesseractOCR   # Windows
```

On Windows the installer does not add Tesseract to `PATH`. Either add
`C:\Program Files\Tesseract-OCR` to it, or set
`pytesseract.pytesseract.tesseract_cmd` to the full `tesseract.exe` path.
Otherwise `pytesseract` raises `TesseractNotFoundError` and every image is
skipped.

## Voice notes

Transcription needs `ffmpeg`, plus a one time download of the Whisper `base`
model (about 150 MB, cached under `~/.cache/huggingface`):

```sh
brew install ffmpeg               # macOS
sudo apt install ffmpeg           # Linux
```

## Database and install

```sh
docker compose up -d      # Postgres 16 + pgvector
uv sync
uv run wadr migrate       # apply schema migrations (migrations/*.sql)
```

## Run

```sh
uv run wadr ingest ./sample_docs
uv run wadr search "tf-idf weighting" --model hybrid
uv run uvicorn wadr.api.app:app
```
