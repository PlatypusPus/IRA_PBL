"""The chat loop behind the web UI.

Deliberately not an LLM. The user's goal is "find that file someone sent me",
and retrieval already answers it - putting a language model in front would add
seconds of latency and the chance of describing a document that does not exist.
The conversation is the interface; the search is the product.

Each turn stores the user's message and the assistant's reply (with the
documents it cited) so a reload does not lose the thread. Threads are grouped
into conversations, which the user can start fresh or delete.
"""

import json
import logging
from dataclasses import asdict

from wadr.accounts import account_ids
from wadr.db import get_conn
from wadr.retrieval import filters, service

log = logging.getLogger(__name__)

HISTORY_LIMIT = 200
TOP_K = 5


class NotYours(Exception):
    """That conversation belongs to someone else, or does not exist."""


def conversations(user_id: int) -> list[dict]:
    """Newest first. The title is the first thing the user asked in it."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT c.id, c.created_at,"
            "       (SELECT m.text FROM chat_messages m WHERE m.conversation_id = c.id"
            "         AND m.role = 'user' ORDER BY m.id LIMIT 1),"
            "       (SELECT count(*) FROM chat_messages m WHERE m.conversation_id = c.id)"
            "  FROM conversations c WHERE c.user_id = %s ORDER BY c.id DESC",
            (user_id,),
        ).fetchall()
    return [
        {"id": r[0], "created_at": r[1].isoformat(), "title": r[2], "messages": r[3]}
        for r in rows
    ]


def start(user_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO conversations (user_id) VALUES (%s) RETURNING id, created_at",
            (user_id,),
        ).fetchone()
    return {"id": row[0], "created_at": row[1].isoformat(), "title": None, "messages": 0}


def delete(user_id: int, conversation_id: int) -> None:
    """Throw a conversation away. Its messages cascade; documents are untouched."""
    with get_conn() as conn:
        row = conn.execute(
            "DELETE FROM conversations WHERE id = %s AND user_id = %s RETURNING id",
            (conversation_id, user_id),
        ).fetchone()
    if row is None:
        raise NotYours(f"no conversation {conversation_id}")


def _own(conn, user_id: int, conversation_id: int) -> None:
    """Guard every conversation-scoped read and write in one place."""
    row = conn.execute(
        "SELECT 1 FROM conversations WHERE id = %s AND user_id = %s",
        (conversation_id, user_id),
    ).fetchone()
    if row is None:
        raise NotYours(f"no conversation {conversation_id}")


def history(user_id: int, conversation_id: int) -> list[dict]:
    with get_conn() as conn:
        _own(conn, user_id, conversation_id)
        rows = conn.execute(
            "SELECT id, role, text, results, created_at FROM chat_messages"
            " WHERE conversation_id = %s ORDER BY created_at DESC, id DESC LIMIT %s",
            (conversation_id, HISTORY_LIMIT),
        ).fetchall()
    return [
        {
            "id": r[0], "role": r[1], "text": r[2],
            "results": r[3] or [], "created_at": r[4].isoformat(),
        }
        for r in reversed(rows)  # newest fetched first, shown oldest first
    ]


def answer(user_id: int, text: str, conversation_id: int | None = None) -> dict:
    """Run one turn. Raises ValueError on a malformed filter token.

    conversation_id=None starts a new conversation, so the very first message
    needs no setup call.
    """
    if conversation_id is None:
        conversation_id = start(user_id)["id"]
    else:
        with get_conn() as conn:
            _own(conn, user_id, conversation_id)
    _store(user_id, "user", text, None, conversation_id)

    with get_conn() as conn:
        linked = account_ids(conn, user_id)
    if not linked:
        return _store(
            user_id, "assistant",
            "No WhatsApp number is linked yet. Open Numbers at the bottom of the "
            "sidebar and connect one - "
            "then everything shared with you becomes searchable here.",
            [], conversation_id,
        )

    results = service.search(text, user_id, top_k=TOP_K)
    payload = [asdict(r) | {"sent_at": r.sent_at.isoformat() if r.sent_at else None}
               for r in results]
    confident = sum(1 for r in results if not r.weak)

    if not results:
        return _store(user_id, "assistant", _nothing_found(text), [], conversation_id)
    # Dense retrieval always returns its nearest k, so "results exist" is not
    # the same as "something matched". If nothing did, say so and offer them as
    # guesses - claiming a match the user can see is wrong destroys trust in
    # every later answer.
    if all(r.weak for r in results):
        return _store(
            user_id, "assistant",
            "Nothing matched that exactly. The closest I have:",
            payload, conversation_id,
        )
    return _store(user_id, "assistant", _found(text, confident), payload, conversation_id)


def _found(text: str, count: int) -> str:
    _, f = filters.parse(text)
    # weak results are shown but not counted as matches
    applied = [
        label for label, value in (
            (f"from {f.sender}", f.sender), (f"in {f.chat}", f.chat),
            (f"before {f.before}", f.before), (f"after {f.after}", f.after),
            (f"{f.doc_type} files", f.doc_type),
        ) if value
    ]
    scope = f" ({', '.join(applied)})" if applied else ""
    return f"{count} document{'s' if count != 1 else ''} matched{scope}."


def _nothing_found(text: str) -> str:
    _, f = filters.parse(text)
    if any([f.sender, f.chat, f.before, f.after, f.doc_type]):
        return (
            "Nothing matched with those filters. Try dropping one of them - "
            "from:, in:, type:, before: and after: all narrow the search."
        )
    return (
        "Nothing matched. Documents only become searchable once they have been "
        "shared with a linked number, and scanned pages need a moment to be read."
    )


def _store(
    user_id: int, role: str, text: str, results: list | None, conversation_id: int
) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO chat_messages (user_id, role, text, results, conversation_id)"
            " VALUES (%s, %s, %s, %s, %s) RETURNING id, created_at",
            (user_id, role, text,
             json.dumps(results) if results is not None else None, conversation_id),
        ).fetchone()
    return {
        "id": row[0], "role": role, "text": text, "results": results or [],
        "created_at": row[1].isoformat(), "conversation_id": conversation_id,
    }
