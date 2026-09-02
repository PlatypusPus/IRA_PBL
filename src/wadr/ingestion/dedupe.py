"""Content-hash dedupe: the same file forwarded around = one document, many sightings."""

import hashlib
from datetime import datetime

import psycopg


def file_hash(file_bytes: bytes) -> str:
    """SHA-256 hex digest - the identity of a document."""
    return hashlib.sha256(file_bytes).hexdigest()


def find_document(conn: psycopg.Connection, hash_: str) -> int | None:
    row = conn.execute("SELECT id FROM documents WHERE file_hash = %s", (hash_,)).fetchone()
    return row[0] if row else None


def insert_document(
    conn: psycopg.Connection,
    hash_: str,
    filename: str,
    mime_type: str,
    extracted_text: str,
    content: bytes,
) -> int:
    row = conn.execute(
        "INSERT INTO documents (file_hash, filename, mime_type, extracted_text, content)"
        " VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (hash_, filename, mime_type, extracted_text, content),
    ).fetchone()
    return row[0]


def add_sighting(
    conn: psycopg.Connection,
    document_id: int,
    sender: str,
    chat: str,
    sent_at: datetime,
    account_id: int | None = None,
) -> None:
    """Record that a document was seen. account_id is the linked WhatsApp number
    that received it, and is what makes the document visible to its owner."""
    conn.execute(
        "INSERT INTO sightings (document_id, sender, chat, sent_at, account_id)"
        " VALUES (%s, %s, %s, %s, %s)",
        (document_id, sender, chat, sent_at, account_id),
    )
