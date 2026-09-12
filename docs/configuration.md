# Configuration

| Env var | Default |
|---|---|
| `WADR_DATABASE_URL` | `postgresql://wadr:wadr@localhost:5433/wadr` |
| `WADR_OLLAMA_URL` | `http://127.0.0.1:11434` |
| `WADR_OPENWA_BRIDGE_URL` | `http://127.0.0.1:8085` (WS1) |

## Why 127.0.0.1 and not localhost

The two HTTP defaults are literal IPv4 on purpose. `localhost` resolves to
`::1` first, both services bind IPv4, and Python's urllib has no Happy Eyeballs
fallback, so it stalls about two seconds per call before retrying IPv4. Keep
the literal IP if you override these on a single machine.
