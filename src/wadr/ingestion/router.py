"""Ingestion entry point: extension -> extractor -> dedupe -> chunk -> index.

This is the single door into the engine. Adapters call ingest(); nothing in
here knows what WhatsApp is.
"""

import logging
import mimetypes
from datetime import datetime
from pathlib import Path

from wadr.db import get_conn
from wadr.indexing import embedder, lexical
from wadr.ingestion import chunker, dedupe
from wadr.ingestion.extractors import audio_asr, docx, image_ocr, pdf, text

log = logging.getLogger(__name__)

EXTRACTORS = {
    ".txt": text.extract,
    ".md": text.extract,
    ".pdf": pdf.extract,
    ".docx": docx.extract,
    ".png": image_ocr.extract,
    ".jpg": image_ocr.extract,
    ".jpeg": image_ocr.extract,
    ".ogg": audio_asr.extract,    # WhatsApp voice notes
    ".opus": audio_asr.extract,
    ".m4a": audio_asr.extract,
}


def _standing_matches(conn, doc_id: int) -> list[tuple[str, str]]:
    """(chat_id, query_text) for every saved search this document satisfies.

    Uses the chunks' tsvector and its GIN index, so it is one indexed query
    rather than one search per standing query.
    """
    return conn.execute(
        "SELECT sq.chat_id, sq.query_text FROM standing_queries sq"
        " WHERE EXISTS (SELECT 1 FROM chunks c WHERE c.document_id = %s"
        "               AND c.tsv @@ websearch_to_tsquery('english', sq.query_text))",
        (doc_id,),
    ).fetchall()


def ingest(
    file_bytes: bytes,
    filename: str,
    sender: str,
    chat: str,
    sent_at: datetime,
    on_standing_match=None,
) -> int | None:
    """Ingest one file; returns its document id, or None if skipped.

    Duplicate content (same SHA-256) only records a new sighting - no
    re-extraction, no re-indexing.
    """
    extractor = EXTRACTORS.get(Path(filename).suffix.lower())
    if extractor is None:
        log.warning("%s: unsupported file type, skipped", filename)
        return None

    hash_ = dedupe.file_hash(file_bytes)
    with get_conn() as conn:
        doc_id = dedupe.find_document(conn, hash_)
        if doc_id is not None:
            dedupe.add_sighting(conn, doc_id, sender, chat, sent_at)
            log.info("%s: duplicate of document %d, sighting recorded", filename, doc_id)
            return doc_id

        try:
            extracted = extractor(file_bytes)
        except Exception as e:  # noqa: BLE001 - deliberately broad
            # Extractors now shell out to tesseract/ffmpeg and parse whatever
            # bytes a chat sends. A corrupt photo, a missing system binary or a
            # NotImplementedError stub must skip ONE file, never abort a folder
            # ingest or turn the WhatsApp webhook into a 500.
            log.warning("%s: extraction failed (%s: %s) - skipped", filename, type(e).__name__, e)
            return None

        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        doc_id = dedupe.insert_document(conn, hash_, filename, mime, extracted, file_bytes)
        dedupe.add_sighting(conn, doc_id, sender, chat, sent_at)

        pieces = chunker.chunk(extracted)
        embeddings = embedder.embed(pieces) if pieces else []
        lexical.index_chunks(conn, doc_id, pieces, embeddings)
        log.info("%s: ingested as document %d (%d chunks)", filename, doc_id, len(pieces))

        # Saved searches. The engine finds the matches and hands them to a
        # callback; it must not know which channel delivers them (see the hard
        # rule in adapters/base.py). A failing notification must not undo an
        # otherwise good ingest, so each one is guarded.
        for chat_id, query_text in _standing_matches(conn, doc_id):
            log.info("standing query %r matched %s -> %s", query_text, filename, chat_id)
            if on_standing_match is not None:
                try:
                    on_standing_match(chat_id, query_text, filename)
                except Exception as e:  # noqa: BLE001
                    log.warning("standing-query notify failed for %s: %s", chat_id, e)
        return doc_id
