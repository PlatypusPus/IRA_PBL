"""WhatsApp adapter.

Architecture: a small Node bridge (bridge/, built on Baileys, see
bridge/index.js) runs as a separate process, owns the WhatsApp session, and
speaks HTTP to WADR. The Python side stays thin: receive webhooks, call the
engine through MessagingInterface, POST replies back. The "openwa" name
survives in routes and this module from the original assignment; the bridge
library is an implementation detail behind an unchanged HTTP contract.

Webhook contract (bridge -> WADR)   [routes live in wadr/api/app.py]
-------------------------------------------------------------------
POST /webhook/openwa         inbound document
    {chat_id, sender, timestamp (ISO-8601), filename, mime_type, data_base64}
    -> 200 {"document_id": 17, "duplicate": false}
POST /webhook/openwa/query   a "/find <query>" chat message
    {chat_id, sender, text}
    -> searches, replies via send_results(); 200 {}
POST /webhook/openwa/get     a "/get <n>" chat message
    {chat_id, sender, text}   (n = result number from the last /find in that chat)
    -> sends that file back via send_file(); 200 {}

Outbound (WADR -> bridge)
-------------------------
POST {WADR_OPENWA_BRIDGE_URL}/send       {chat_id, text}
POST {WADR_OPENWA_BRIDGE_URL}/send-file  {chat_id, filename, mime_type, data_base64}
Env: WADR_OPENWA_BRIDGE_URL, default http://localhost:8085.
"""

import base64
import json
import os
import urllib.request
from datetime import datetime

from wadr.adapters.base import MessagingInterface
from wadr.db import get_conn
from wadr.ingestion import dedupe
from wadr.models import SearchResult
from wadr.retrieval import service

# chat_id -> document_ids of that chat's last /find, so "/get <n>" can resolve n.
# ponytail: in-memory, unbounded, resets on restart - fine at personal scale;
# move to a table if it must survive restarts or memory needs bounding.
_last_results: dict[str, list[int]] = {}


def _post(route: str, body: dict) -> None:
    bridge = os.environ.get("WADR_OPENWA_BRIDGE_URL", "http://localhost:8085")
    req = urllib.request.Request(
        bridge + route,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=30)


class OpenWAAdapter(MessagingInterface):
    def handle_webhook(self, payload: dict) -> dict:
        """Validate + decode an inbound bridge payload, delegate to on_document()."""
        file_bytes = base64.b64decode(payload["data_base64"], validate=True)
        sent_at = datetime.fromisoformat(payload["timestamp"])
        # ponytail: pre-check the hash here because router.ingest() returns the
        # same id for new and duplicate docs; cheaper than changing its contract.
        with get_conn() as conn:
            duplicate = dedupe.find_document(conn, dedupe.file_hash(file_bytes)) is not None
        doc_id = self.on_document(
            file_bytes, payload["filename"], payload["sender"], payload["chat_id"], sent_at
        )
        return {"document_id": doc_id, "duplicate": duplicate}

    def handle_query(self, payload: dict) -> None:
        """A '/find <query>' message: search, remember the hits for /get, reply."""
        chat_id = payload["chat_id"]
        query = payload.get("text", "").removeprefix("/find").strip()
        if not query:
            self.send_text(chat_id, "Usage: /find <query>")
            return
        results = service.search(query)
        _last_results[chat_id] = [r.document_id for r in results]
        self.send_results(chat_id, results)

    def handle_get(self, payload: dict) -> None:
        """A '/get <n>' message: send back the nth file from the last /find."""
        chat_id = payload["chat_id"]
        results = _last_results.get(chat_id)
        if not results:
            self.send_text(chat_id, "Search first with /find <query>, then /get <number>.")
            return
        arg = payload.get("text", "").removeprefix("/get").strip()
        if not arg.isdigit() or not (1 <= int(arg) <= len(results)):
            self.send_text(chat_id, f"Usage: /get <1-{len(results)}> (from your last search).")
            return
        doc_id = results[int(arg) - 1]
        with get_conn() as conn:
            row = conn.execute(
                "SELECT filename, mime_type, content FROM documents WHERE id = %s", (doc_id,)
            ).fetchone()
        if not row or row[2] is None:
            self.send_text(chat_id, "That file isn't stored - re-share it, then /get again.")
            return
        self.send_file(chat_id, row[0], row[1], bytes(row[2]))

    def send_results(self, chat_id: str, results: list[SearchResult]) -> None:
        """Format results as one WhatsApp message and POST it to the bridge /send."""
        if not results:
            self.send_text(chat_id, "No results.")
            return
        lines = [
            f"{i}. *{r.filename}*{r.provenance()}\n{r.snippet}"
            for i, r in enumerate(results, start=1)
        ]
        lines.append("\nReply /get <number> to receive a file.")
        self.send_text(chat_id, "\n".join(lines))

    def send_text(self, chat_id: str, text: str) -> None:
        _post("/send", {"chat_id": chat_id, "text": text})

    def send_file(self, chat_id: str, filename: str, mime_type: str, data: bytes) -> None:
        _post(
            "/send-file",
            {
                "chat_id": chat_id,
                "filename": filename,
                "mime_type": mime_type,
                "data_base64": base64.b64encode(data).decode(),
            },
        )
