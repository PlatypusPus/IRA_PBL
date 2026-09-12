# Configuration

All settings are environment variables, read from `.env` or the shell.

| Env var | Default | Notes |
|---|---|---|
| `WADR_DATABASE_URL` | `postgresql://wadr:wadr@localhost:5433/wadr` | Matches `docker-compose.yml` |
| `WADR_OLLAMA_URL` | `http://127.0.0.1:11434` | Unreachable means keyword only search |
| `WADR_EMBED_MODEL` | `nomic-embed-text` | `ollama pull` it first |
| `WADR_SUMMARY_MODEL` | *(unset)* | Unset means digests fall back to opening sentences |
| `WADR_BRIDGE_URL` | `http://127.0.0.1:8085` | Where the API reaches the bridge |
| `WADR_BRIDGE_TOKEN` | *(required)* | Same value in both processes; written on first `npm start` |
| `WADR_API_KEY` | *(unset)* | MCP server only, the agent's key |
