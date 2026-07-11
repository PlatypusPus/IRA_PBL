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
    conn: psycopg.Connection, hash_: str, filename: str, mime_type: str, extracted_text: str
) -> int:
    row = conn.execute(
        "INSERT INTO documents (file_hash, filename, mime_type, extracted_text)"
        " VALUES (%s, %s, %s, %s) RETURNING id",
        (hash_, filename, mime_type, extracted_text),
    ).fetchone()
    return row[0]


def add_sighting(
    conn: psycopg.Connection, document_id: int, sender: str, chat: str, sent_at: datetime
) -> None:
    conn.execute(
        "INSERT INTO sightings (document_id, sender, chat, sent_at) VALUES (%s, %s, %s, %s)",
        (document_id, sender, chat, sent_at),
    )
