# WADR TODO

## Product
- Auth/session features: signup, login, logout, accounts, API keys
- Chat: conversations, history, messaging
- Digests: scheduled document summaries
- MCP server: AI assistant integration
- Summaries: document summarization pipeline

## Infrastructure
- CI: GitHub Actions on push/PR
- Health endpoint: GET /health
- docker-compose healthcheck on db

## Known Issues
- Tesseract not installed in dev env - 4 OCR tests fail
- Postgres auth fails in some environments - 5 DB tests fail
- OCR fallback when tesseract unavailable keeps text layer

## Audit Fixes Applied
- pdf.py: keep text layer when OCR fails (not discard it)
- bridge routes: psycopg.OperationalError -> 503
- service.search(): empty query guard
- Empty .env.example + CI workflow + docker-compose healthcheck
