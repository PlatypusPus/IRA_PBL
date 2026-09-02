"""Users, sessions and linked WhatsApp numbers.

Password hashing is `hashlib.scrypt` from the standard library rather than
bcrypt/argon2 - one less dependency, and scrypt is a memory-hard KDF that the
stdlib exposes with sane knobs. Parameters below are the interactive-login set
from the scrypt paper (n=2**14, r=8, p=1, ~16 MB per hash).
"""

import hashlib
import os
import re
import secrets
from datetime import UTC, datetime, timedelta

import psycopg

from wadr.db import get_conn

SESSION_DAYS = 30
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1

# Deliberately permissive: an over-clever regex rejects real addresses. Real
# validation is "we sent you mail", which this product does not do yet.
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8


class AuthError(Exception):
    """Bad credentials, duplicate signup, or an invalid session."""


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.scrypt(
        password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32
    )
    return f"scrypt${salt.hex()}${key.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, key_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        key = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex),
            n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32,
        )
    except (ValueError, TypeError):
        return False
    # constant time: a timing difference here leaks the hash prefix
    return secrets.compare_digest(key.hex(), key_hex)


def sign_up(email: str, password: str) -> int:
    email = email.strip().lower()
    if not EMAIL.match(email):
        raise AuthError("that does not look like an email address")
    if len(password) < MIN_PASSWORD:
        raise AuthError(f"password must be at least {MIN_PASSWORD} characters")
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email = %s", (email,)).fetchone():
            raise AuthError("an account with that email already exists")
        return conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id",
            (email, hash_password(password)),
        ).fetchone()[0]


def log_in(email: str, password: str) -> str:
    """Verify credentials and return a fresh session token."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = %s", (email.strip().lower(),)
        ).fetchone()
    # Same message either way: distinguishing them tells an attacker which
    # emails are registered.
    if row is None or not verify_password(password, row[1]):
        raise AuthError("wrong email or password")
    return _new_session(row[0])


def _new_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (%s, %s, %s)",
            (token, user_id, datetime.now(UTC) + timedelta(days=SESSION_DAYS)),
        )
    return token


def user_for_token(token: str | None) -> dict | None:
    """Resolve a session token to {id, email}, or None if absent/expired."""
    if not token:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT u.id, u.email FROM sessions s JOIN users u ON u.id = s.user_id"
            " WHERE s.token = %s AND s.expires_at > now()",
            (token,),
        ).fetchone()
    return {"id": row[0], "email": row[1]} if row else None


def log_out(token: str | None) -> None:
    if not token:
        return
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token = %s", (token,))


# --------------------------------------------------------------- WhatsApp numbers


def list_accounts(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT a.id, a.label, a.phone, a.session_key, a.status,"
            "       (SELECT count(DISTINCT s.document_id) FROM sightings s"
            "         WHERE s.account_id = a.id)"
            "  FROM whatsapp_accounts a WHERE a.user_id = %s ORDER BY a.id",
            (user_id,),
        ).fetchall()
    return [
        {
            "id": r[0], "label": r[1], "phone": r[2], "session_key": r[3],
            "status": r[4], "documents": r[5],
        }
        for r in rows
    ]


def create_account(user_id: int, label: str) -> dict:
    """Reserve a slot for a new number. The bridge starts a WhatsApp session
    named session_key; linking finishes when the user scans the QR."""
    session_key = f"u{user_id}-{secrets.token_hex(4)}"
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO whatsapp_accounts (user_id, label, session_key)"
            " VALUES (%s, %s, %s) RETURNING id",
            (user_id, label.strip() or "My WhatsApp", session_key),
        ).fetchone()
    return {
        "id": row[0], "label": label.strip() or "My WhatsApp", "phone": None,
        "session_key": session_key, "status": "pending", "documents": 0,
    }


def delete_account(user_id: int, account_id: int) -> str:
    """Unlink a number. Returns its session_key so the caller can stop the
    bridge session. Sightings cascade; the documents themselves stay, because
    another user's number may have seen the same file."""
    with get_conn() as conn:
        row = conn.execute(
            "DELETE FROM whatsapp_accounts WHERE id = %s AND user_id = %s"
            " RETURNING session_key",
            (account_id, user_id),
        ).fetchone()
    if row is None:
        raise AuthError("no such linked number")
    return row[0]


def account_ids(conn: psycopg.Connection, user_id: int) -> list[int]:
    return [
        r[0] for r in conn.execute(
            "SELECT id FROM whatsapp_accounts WHERE user_id = %s", (user_id,)
        ).fetchall()
    ]


def account_for_session_key(session_key: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, user_id FROM whatsapp_accounts WHERE session_key = %s",
            (session_key,),
        ).fetchone()
    return {"id": row[0], "user_id": row[1]} if row else None


def mark_linked(session_key: str, phone: str | None, status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE whatsapp_accounts SET status = %s,"
            "       phone = COALESCE(%s, phone) WHERE session_key = %s",
            (status, phone, session_key),
        )


# ------------------------------------------------------------------ API keys


KEY_PREFIX = "wadr_"


def _key_hash(key: str) -> str:
    # Plain SHA-256, not scrypt: an API key is 32 bytes of entropy from
    # secrets.token_urlsafe, so there is no dictionary to attack and no reason
    # to pay a KDF's cost on every agent call.
    return hashlib.sha256(key.encode()).hexdigest()


def create_api_key(user_id: int, label: str = "") -> str:
    """Mint a key. Returned in full exactly once - only its hash is stored."""
    key = KEY_PREFIX + secrets.token_urlsafe(32)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO api_keys (user_id, label, key_hash, prefix)"
            " VALUES (%s, %s, %s, %s)",
            (user_id, label.strip() or "Agent key", _key_hash(key), key[:12]),
        )
    return key


def user_for_api_key(key: str | None) -> dict | None:
    """Resolve a key to {id, email}, or None. Also stamps last_used_at."""
    if not key:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "UPDATE api_keys SET last_used_at = now() WHERE key_hash = %s"
            " RETURNING user_id",
            (_key_hash(key),),
        ).fetchone()
        if row is None:
            return None
        user = conn.execute(
            "SELECT id, email FROM users WHERE id = %s", (row[0],)
        ).fetchone()
    return {"id": user[0], "email": user[1]} if user else None


def list_api_keys(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, label, prefix, created_at, last_used_at FROM api_keys"
            " WHERE user_id = %s ORDER BY id",
            (user_id,),
        ).fetchall()
    return [
        {
            "id": r[0], "label": r[1], "prefix": r[2],
            "created_at": r[3].isoformat(),
            "last_used_at": r[4].isoformat() if r[4] else None,
        }
        for r in rows
    ]


def revoke_api_key(user_id: int, key_id: int) -> None:
    with get_conn() as conn:
        row = conn.execute(
            "DELETE FROM api_keys WHERE id = %s AND user_id = %s RETURNING id",
            (key_id, user_id),
        ).fetchone()
    if row is None:
        raise AuthError("no such key")
