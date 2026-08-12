import os
from datetime import datetime

import pytest

from wadr.ingestion import dedupe


def test_same_bytes_same_hash():
    assert dedupe.file_hash(b"abc") == dedupe.file_hash(b"abc")


def test_different_bytes_different_hash():
    assert dedupe.file_hash(b"abc") != dedupe.file_hash(b"abd")


def test_hash_is_sha256_hex():
    h = dedupe.file_hash(b"")
    assert len(h) == 64
    int(h, 16)  # raises if not hex


def _db_conn():
    import psycopg

    from wadr.db import DATABASE_URL

    try:
        return psycopg.connect(DATABASE_URL, connect_timeout=2)
    except psycopg.OperationalError:
        pytest.skip("Postgres not running - `docker compose up -d` to enable this test")


def test_duplicate_content_is_one_document_with_new_sighting():
    """Integration: same bytes twice -> one documents row, two sightings.

    Runs inside a never-committed transaction, so it leaves no rows behind.
    """
    conn = _db_conn()
    try:
        data = b"dedupe-test-" + os.urandom(8)
        h = dedupe.file_hash(data)
        assert dedupe.find_document(conn, h) is None

        doc_id = dedupe.insert_document(conn, h, "a.txt", "text/plain", "hello", data)
        dedupe.add_sighting(conn, doc_id, "alice", "family chat", datetime(2026, 1, 1))

        # the same file arrives again, forwarded to another chat
        assert dedupe.find_document(conn, h) == doc_id
        dedupe.add_sighting(conn, doc_id, "bob", "project group", datetime(2026, 1, 2))

        n = conn.execute(
            "SELECT count(*) FROM sightings WHERE document_id = %s", (doc_id,)
        ).fetchone()[0]
        assert n == 2
    finally:
        conn.rollback()
        conn.close()
