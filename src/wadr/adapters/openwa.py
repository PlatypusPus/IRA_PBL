"""WhatsApp adapter.

The Node bridge (bridge/) owns every WhatsApp session - one per linked number,
each identified by its account's session_key. Every payload from the bridge
carries that key, which is how a document is attributed to the right user.

Webhook contract (bridge -> WADR)   [routes live in wadr/api/app.py]
-------------------------------------------------------------------
POST /api/bridge/document   inbound file
    {session_key, chat_id, sender, timestamp (ISO-8601), filename,
     mime_type, data_base64}
    -> 200 {"document_id": 17, "duplicate": false}
POST /api/bridge/query      a "/find <query>" message typed in WhatsApp
POST /api/bridge/get        a "/get <n>" message
    {session_key, chat_id, sender, text, from_me}
    from_me says the owner typed it. Anyone else searches only what they can
    already see - see _seen_by().
POST /api/bridge/status     session went linked / logged out

All four require the X-Bridge-Token shared secret.

Replies go back out through api/bridge_client.py, addressed to the same
session_key, so an answer always leaves from the number the question arrived on.
"""

import base64
from datetime import datetime

from wadr.accounts import account_for_session_key
from wadr.adapters.base import MessagingInterface
from wadr.api import bridge_client
from wadr.db import get_conn
from wadr.ingestion import dedupe
from wadr.models import SearchResult
from wadr.retrieval import service

# (session_key, chat_id, sender) -> document_ids of that person's last /find, so
# "/get <n>" can resolve n. Keyed by sender too, or two people searching in one
# group would renumber each other's results. ponytail: in-memory, unbounded,
# resets on restart - fine at personal scale; move to a table if it must survive.
_last_results: dict[tuple[str, str, str], list[int]] = {}


def _key(payload: dict) -> tuple[str, str, str]:
    return (payload["session_key"], payload["chat_id"], payload.get("sender") or "")


def _seen_by(payload: dict) -> tuple[str, str] | None:
    """Who is asking, for search scoping - or None when it is the owner.

    A linked number sits in group chats full of other people, and /find is
    typed by whoever feels like typing it. Only the owner (from_me: the message
    came from this very WhatsApp) gets to search everything the number ever
    received; anyone else sees only what they could already see - files they
    sent, or files shared in the chat they are asking in.
    """
    if payload.get("from_me"):
        return None
    return (payload.get("sender") or "", payload["chat_id"])


class UnknownSession(ValueError):
    """The bridge reported a session_key with no linked number behind it."""


class OpenWAAdapter(MessagingInterface):
    def __init__(self, session_key: str | None = None) -> None:
        self.session_key = session_key

    # ------------------------------------------------------------ inbound

    def handle_webhook(self, payload: dict) -> dict:
        """Validate + decode an inbound bridge payload, delegate to on_document()."""
        session_key = payload["session_key"]
        account = account_for_session_key(session_key)
        if account is None:
            raise UnknownSession(f"no linked number for session {session_key!r}")
        self.session_key = session_key

        file_bytes = base64.b64decode(payload["data_base64"], validate=True)
        sent_at = datetime.fromisoformat(payload["timestamp"])
        # ponytail: pre-check the hash because router.ingest() returns the same
        # id for new and duplicate docs; cheaper than changing its contract.
        with get_conn() as conn:
            duplicate = dedupe.find_document(conn, dedupe.file_hash(file_bytes)) is not None
        doc_id = self.on_document(
            file_bytes, payload["filename"], payload["sender"],
            payload["chat_id"], sent_at, account["id"],
        )
        return {"document_id": doc_id, "duplicate": duplicate}

    def handle_query(self, payload: dict) -> None:
        """A '/find <query>' message: search that number's owner's documents."""
        session_key, chat_id = payload["session_key"], payload["chat_id"]
        account = account_for_session_key(session_key)
        if account is None:
            raise UnknownSession(f"no linked number for session {session_key!r}")
        self.session_key = session_key

        query = payload.get("text", "").removeprefix("/find").strip()
        if not query:
            self.send_text(chat_id, "Usage: /find <query>")
            return
        seen_by = _seen_by(payload)
        try:
            results = service.search(query, account["user_id"], seen_by=seen_by)
        except ValueError as e:  # malformed filter token
            self.send_text(chat_id, str(e))
            return
        _last_results[_key(payload)] = [r.document_id for r in results]
        if not results and seen_by is not None:
            self.send_text(
                chat_id,
                "No results. Here I only search files shared in this chat or "
                "sent by you - not the rest of this WhatsApp's documents.",
            )
            return
        self.send_results(chat_id, results)

    def handle_get(self, payload: dict) -> None:
        """A '/get <n>' message: send back the nth file from the last /find."""
        session_key, chat_id = payload["session_key"], payload["chat_id"]
        account = account_for_session_key(session_key)
        if account is None:
            raise UnknownSession(f"no linked number for session {session_key!r}")
        self.session_key = session_key

        results = _last_results.get(_key(payload))
        if not results:
            self.send_text(chat_id, "Search first with /find <query>, then /get <number>.")
            return
        arg = payload.get("text", "").removeprefix("/get").strip()
        if not arg.isdigit() or not (1 <= int(arg) <= len(results)):
            self.send_text(chat_id, f"Usage: /get <1-{len(results)}> (from your last search).")
            return
        # Re-check at send time, against the same visibility rules the search
        # used: owning the number is not enough if the asker is someone else.
        found = service.get_document(
            results[int(arg) - 1], account["user_id"], seen_by=_seen_by(payload)
        )
        if found is None:
            self.send_text(chat_id, "That file isn't stored - re-share it, then /get again.")
            return
        filename, mime_type, content = found
        self.send_file(chat_id, filename, mime_type, content)

    # ----------------------------------------------------------- outbound

    def send_results(self, chat_id: str, results: list[SearchResult]) -> None:
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
        bridge_client.send_text(self.session_key, chat_id, text)

    def send_file(self, chat_id: str, filename: str, mime_type: str, data: bytes) -> None:
        bridge_client.send_file(
            self.session_key, chat_id, filename, mime_type, base64.b64encode(data).decode()
        )

    def notify_standing_match(self, chat_id: str, query_text: str, filename: str) -> None:
        self.send_text(chat_id, f'New document matching "{query_text}": {filename}')
