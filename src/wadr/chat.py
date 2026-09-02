"""The chat loop behind the web UI.

Deliberately not an LLM. The user's goal is "find that file someone sent me",
and retrieval already answers it - putting a language model in front would add
seconds of latency and the chance of describing a document that does not exist.
The conversation is the interface; the search is the product.

Each turn stores the user's message and the assistant's reply (with the
documents it cited) so a reload does not lose the thread.
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


def history(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, role, text, results, created_at FROM chat_messages"
            " WHERE user_id = %s ORDER BY created_at DESC, id DESC LIMIT %s",
            (user_id, HISTORY_LIMIT),
        ).fetchall()
    return [
        {
            "id": r[0], "role": r[1], "text": r[2],
            "results": r[3] or [], "created_at": r[4].isoformat(),
        }
        for r in reversed(rows)  # newest fetched first, shown oldest first
    ]


def answer(user_id: int, text: str) -> dict:
    """Run one turn. Raises ValueError on a malformed filter token."""
    _store(user_id, "user", text, None)

    with get_conn() as conn:
        linked = account_ids(conn, user_id)
    if not linked:
        return _store(
            user_id, "assistant",
            "No WhatsApp number is linked yet. Open Numbers and connect one - "
            "then everything shared with you becomes searchable here.",
            [],
        )

    results = service.search(text, user_id, top_k=TOP_K)
    payload = [asdict(r) | {"sent_at": r.sent_at.isoformat() if r.sent_at else None}
               for r in results]
    confident = sum(1 for r in results if not r.weak)

    if not results:
        return _store(user_id, "assistant", _nothing_found(text), [])
    # Dense retrieval always returns its nearest k, so "results exist" is not
    # the same as "something matched". If nothing did, say so and offer them as
    # guesses - claiming a match the user can see is wrong destroys trust in
    # every later answer.
    if all(r.weak for r in results):
        return _store(
            user_id, "assistant",
            "Nothing matched that exactly. The closest I have:",
            payload,
        )
    return _store(user_id, "assistant", _found(text, confident), payload)


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


def _store(user_id: int, role: str, text: str, results: list | None) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO chat_messages (user_id, role, text, results)"
            " VALUES (%s, %s, %s, %s) RETURNING id, created_at",
            (user_id, role, text, json.dumps(results) if results is not None else None),
        ).fetchone()
    return {
        "id": row[0], "role": role, "text": text,
        "results": results or [], "created_at": row[1].isoformat(),
    }
