# WhatsApp bridge

Needs [Node 18+](https://nodejs.org). The bridge owns the WhatsApp session and
forwards documents and `/find` queries to the API. The contract is in
`src/wadr/adapters/openwa.py`.

## Run it

```sh
uv run uvicorn wadr.api.app:app        # terminal 1: the WADR API
cd bridge && npm install && npm start  # terminal 2: the bridge
```

Open <http://localhost:8085> and scan the QR with WhatsApp
(**Linked devices > Link a device**).

## Commands

- **Send any PDF or document** to ingest it. The bridge reacts with a tick
  (saved), a paperclip (already had it), or a cross (failed), so the sender is
  not left guessing.
- **`/find <query>`** searches and replies with a ranked list.
- **`/get <n>`** sends back the nth file from your last `/find`.

Re-forwarding a known file records a sighting, not a new document. Files
ingested before the `content` column (migration 0002) cannot be fetched with
`/get` until they are re-shared.

## Configuration

The bridge reads an optional `.env` at the repo root using Node's native
`--env-file-if-exists`, with no dotenv dependency. For example set
`WADR_API=http://localhost:8017` if port 8000 is busy, then run uvicorn with
`--port 8017`.

## Why Baileys

Both open-wa and whatsapp-web.js were tried and both broke on media download
against current WhatsApp Web. They drive a real browser page and call WhatsApp
internals that keep changing. [Baileys](https://github.com/WhiskeySockets/Baileys)
speaks the protocol directly and decrypts media itself, with no browser.

Route and adapter names keep `openwa` from the original assignment. The bridge
library sits behind an unchanged HTTP contract.
