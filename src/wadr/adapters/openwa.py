"""open-wa WhatsApp adapter - SKELETON. TODO(WS1).

Architecture: a small Node bridge (github.com/open-wa/wa-automate-nodejs) runs
as a separate process, owns the WhatsApp session, and speaks HTTP to WADR.
The Python side stays thin: receive webhooks, call the engine through
MessagingInterface, POST replies back. Put the bridge in bridge/ (new, Node) -
it is out of scope for this repo's Python tests.

Webhook contract (bridge -> WADR)
---------------------------------
POST {WADR_API}/webhook/openwa            (route stub lives in wadr/api/app.py)
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

from wadr.adapters.base import MessagingInterface
from wadr.models import SearchResult


class OpenWAAdapter(MessagingInterface):
    def handle_webhook(self, payload: dict) -> dict:
        """Validate + decode an inbound bridge payload, delegate to on_document().

        Decode data_base64, parse the ISO timestamp, then return
        {"document_id": <id or None>, "duplicate": <bool>}.
        """
        raise NotImplementedError("TODO(WS1): open-wa inbound webhook")

    def send_results(self, chat_id: str, results: list[SearchResult]) -> None:
        """Format results as one WhatsApp message and POST it to the bridge /send."""
        raise NotImplementedError("TODO(WS1): open-wa outbound send")
