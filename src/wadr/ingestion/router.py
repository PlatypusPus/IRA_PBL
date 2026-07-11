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
    ".docx": docx.extract,        # TODO(WS2)
    ".png": image_ocr.extract,    # TODO(WS2)
    ".jpg": image_ocr.extract,    # TODO(WS2)
    ".jpeg": image_ocr.extract,   # TODO(WS2)
    ".ogg": audio_asr.extract,    # TODO(WS2) - WhatsApp voice notes
    ".opus": audio_asr.extract,   # TODO(WS2)
    ".m4a": audio_asr.extract,    # TODO(WS2)
}


def ingest(
    file_bytes: bytes, filename: str, sender: str, chat: str, sent_at: datetime
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
        except NotImplementedError as e:
            log.warning("%s: %s - skipped", filename, e)
            return None

        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        doc_id = dedupe.insert_document(conn, hash_, filename, mime, extracted)
        dedupe.add_sighting(conn, doc_id, sender, chat, sent_at)

        pieces = chunker.chunk(extracted)
        embeddings = embedder.embed(pieces) if pieces else []
        lexical.index_chunks(conn, doc_id, pieces, embeddings)
        # TODO(WS4): standing-query matching - run the new document against
        # standing_queries and push hits to their chat_id via the active
        # adapter's send_results().
        log.info("%s: ingested as document %d (%d chunks)", filename, doc_id, len(pieces))
        return doc_id
