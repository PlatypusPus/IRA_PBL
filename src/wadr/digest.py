"""The weekly "what did I miss" digest.

Documents arrive in group chats nobody reads to the end. Once a week WADR
sends each user a list of what actually landed on their numbers - delivered to
the number itself, so the summary shows up in the same app the documents did.

Run it from cron or Task Scheduler:

    uv run wadr digest             # every linked user
    uv run wadr digest --dry-run   # print, send nothing
"""

import logging
from datetime import UTC, datetime, timedelta

import psycopg

from wadr.api import bridge_client
from wadr.db import get_conn

log = logging.getLogger(__name__)

DEFAULT_DAYS = 7
MAX_LISTED = 15  # a message nobody scrolls to the end of is a message nobody reads


def _since(conn: psycopg.Connection, user_id: int, days: int) -> datetime:
    """Where the last digest stopped, or `days` ago on the very first run.

    Anchoring on the previous run means a missed week widens the next digest
    instead of dropping the documents it should have covered.
    """
    row = conn.execute(
        "SELECT last_sent_at FROM digest_runs WHERE user_id = %s", (user_id,)
    ).fetchone()
    return row[0] if row else datetime.now(UTC) - timedelta(days=days)


def _arrivals(
    conn: psycopg.Connection, user_id: int, since: datetime
) -> list[tuple[str, str, datetime]]:
    """(filename, sender, received) for everything this user's numbers got since.

    ponytail: no LIMIT - a week of one person's documents is small, and the
    count in the message has to be the real one.
    """
    return conn.execute(
        "SELECT d.filename, min(s.sender), max(s.sent_at)"
        "  FROM documents d"
        "  JOIN sightings s ON s.document_id = d.id"
        "  JOIN whatsapp_accounts w ON w.id = s.account_id"
        " WHERE w.user_id = %s AND s.sent_at > %s"
        " GROUP BY d.id, d.filename"
        " ORDER BY max(s.sent_at) DESC",
        (user_id, since),
    ).fetchall()


def compose(arrivals: list[tuple[str, str, datetime]]) -> str:
    lines = [f"• {name} — from {sender}" for name, sender, _ in arrivals[:MAX_LISTED]]
    if len(arrivals) > MAX_LISTED:
        lines.append(f"…and {len(arrivals) - MAX_LISTED} more")
    plural = "" if len(arrivals) == 1 else "s"
    return "\n".join([
        f"*{len(arrivals)} new document{plural}* since your last digest:",
        "",
        *lines,
        "",
        "Send /find <words> to pull any of them back.",
    ])


def build(user_id: int, days: int = DEFAULT_DAYS) -> str | None:
    """The digest text for one user, or None if nothing new arrived."""
    with get_conn() as conn:
        arrivals = _arrivals(conn, user_id, _since(conn, user_id, days))
    return compose(arrivals) if arrivals else None


def _delivery(conn: psycopg.Connection, user_id: int) -> tuple[str, str] | None:
    """(session_key, self-chat id) for the number the digest is sent to.

    ponytail: the first linked number, even when several are linked - one
    digest covering all of them beats N near-identical messages.
    """
    row = conn.execute(
        "SELECT session_key, phone FROM whatsapp_accounts"
        " WHERE user_id = %s AND status = 'linked' AND phone IS NOT NULL"
        " ORDER BY id LIMIT 1",
        (user_id,),
    ).fetchone()
    return (row[0], f"{row[1]}@s.whatsapp.net") if row else None


def send(user_id: int, days: int = DEFAULT_DAYS, dry_run: bool = False) -> str | None:
    """Build and deliver one user's digest. Returns the text, or None."""
    with get_conn() as conn:
        arrivals = _arrivals(conn, user_id, _since(conn, user_id, days))
    if not arrivals:
        return None
    text = compose(arrivals)
    if dry_run:
        return text

    with get_conn() as conn:
        target = _delivery(conn, user_id)
    if target is None:
        log.warning("user %s has no connected number to send a digest to", user_id)
        return None

    session_key, chat_id = target
    result = bridge_client.send_text(session_key, chat_id, text)
    # The bridge answers {} on success and {"status": ...} on failure. Only mark
    # the window consumed if it really went out, otherwise a bridge that was
    # down for the weekly run erases the week it failed to report.
    if result.get("status"):
        log.warning("digest for user %s not sent: %s", user_id, result.get("detail"))
        return None

    # GREATEST(now(), newest thing reported): sent_at is WhatsApp's timestamp,
    # taken from the sender's phone, so it can sit slightly in the future
    # relative to this database. Marking the window with now() alone would then
    # report the same document again in every digest until the clocks met.
    high_water = max(a[2] for a in arrivals)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO digest_runs (user_id, last_sent_at)"
            " VALUES (%s, GREATEST(now(), %s))"
            " ON CONFLICT (user_id) DO UPDATE SET last_sent_at = EXCLUDED.last_sent_at",
            (user_id, high_water),
        )
    return text


def send_all(days: int = DEFAULT_DAYS, dry_run: bool = False) -> dict[int, str]:
    """Digest every user with a connected number. Returns {user_id: text} sent."""
    with get_conn() as conn:
        user_ids = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT user_id FROM whatsapp_accounts WHERE status = 'linked'"
            ).fetchall()
        ]
    sent = {}
    for user_id in user_ids:
        try:
            text = send(user_id, days, dry_run)
        except Exception as e:  # noqa: BLE001 - one broken account must not stop the run
            log.warning("digest failed for user %s: %s", user_id, e)
            continue
        if text:
            sent[user_id] = text
    return sent
