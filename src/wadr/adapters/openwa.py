"""WhatsApp adapter.

Architecture: a small Node bridge (bridge/, built on Baileys, see
bridge/index.js) runs as a separate process, owns the WhatsApp session, and
speaks HTTP to WADR. The Python side stays thin: receive webhooks, call the
engine through MessagingInterface, POST replies back. The "openwa" name
survives in routes and this module from the original assignment; the bridge
library is an implementation detail behind an unchanged HTTP contract.

Webhook contract (bridge -> WADR)
---------------------------------
POST {WADR_API}/webhook/openwa            (route lives in wadr/api/app.py)
    {
      "chat_id":     "1234567890-123456@g.us",
      "sender":      "+91xxxxxxxxxx",
      "timestamp":   "2026-07-11T14:03:22+05:30",    # ISO-8601
      "filename":    "invoice_oct.pdf",
      "mime_type":   "application/pdf",
      "data_base64": "<file bytes, base64>"
    }
    -> 200 {"document_id": 17, "duplicate": false}

The bridge also forwards chat messages starting with "/find " as queries:
POST {WADR_API}/webhook/openwa/query
    {"chat_id": "...", "sender": "...", "text": "/find invoice"}
    -> WADR searches and replies via send_results(); returns 200 {}.

Outbound (WADR -> bridge)
-------------------------
POST {WADR_OPENWA_BRIDGE_URL}/send  {"chat_id": "...", "text": "<formatted results>"}
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

    def send_results(self, chat_id: str, results: list[SearchResult]) -> None:
        """Format results as one WhatsApp message and POST it to the bridge /send."""
        if not results:
            text = "No results."
        else:
            text = "\n".join(
                f"{i}. *{r.filename}*  (doc {r.document_id}, score {r.score:.4f})\n{r.snippet}"
                for i, r in enumerate(results, start=1)
            )
        bridge = os.environ.get("WADR_OPENWA_BRIDGE_URL", "http://localhost:8085")
        req = urllib.request.Request(
            f"{bridge}/send",
            data=json.dumps({"chat_id": chat_id, "text": text}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=15)
