"""One-line summaries of ingested documents.

A list of filenames tells you nothing when the filename is
`wa-1788370118.jpeg`, which is what WhatsApp calls a photographed notice. This
turns each one into a sentence saying what it actually is.

A local Ollama chat model writes it when one is configured
(`WADR_SUMMARY_MODEL`, e.g. `llama3.2:3b`). With no model configured, or with
Ollama down, it falls back to the document's own opening sentence - worse, but
never absent. This runs on a schedule, where a hard dependency on a model
nobody pulled would mean no digest at all.

Summaries are generated here rather than during ingest: an LLM call on the
webhook path would hold WhatsApp's delivery open for seconds per file.
"""

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request

import psycopg

from wadr.db import get_conn
from wadr.indexing.embedder import OLLAMA_URL

log = logging.getLogger(__name__)

# Empty = no chat model, use the opening sentence. Any model Ollama can run
# will do; a 3B is plenty for one sentence about one page.
MODEL = os.environ.get("WADR_SUMMARY_MODEL", "")
MAX_CHARS = 140      # one line in a WhatsApp message
INPUT_CHARS = 3_000  # first page or so - enough to say what a document is
# Generous: the FIRST call pays for loading the model into memory (measured at
# over 60s for llama3.2:3b on a cold Ollama), while every call after it takes
# about a second. This runs as a scheduled batch, so waiting once is free.
TIMEOUT = 300

PROMPT = (
    "Summarise this document in ONE short sentence, at most 20 words. Say what "
    "kind of document it is and what it concerns. Reply with the sentence only "
    "- no preamble, no quotes, no bullet points. Do not open with \"This is\" "
    "or \"This document\": name the thing directly.\n\nDocument:\n"
)

_warned = False


def _generate(text: str) -> str | None:
    """Ask Ollama for a sentence. None when it cannot answer."""
    global _warned
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=json.dumps({
            "model": MODEL,
            "prompt": PROMPT + text[:INPUT_CHARS],
            "stream": False,
            # Deterministic and short: the same document should not get a
            # different summary each run, and we only want one sentence.
            "options": {"temperature": 0, "num_predict": 60},
        }).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.load(response)["response"]
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as e:
        if not _warned:
            log.warning(
                "summary model %r unavailable at %s (%s) - falling back to the "
                "document's opening line. Fix: ollama pull %s",
                MODEL, OLLAMA_URL, e, MODEL or "llama3.2:3b",
            )
            _warned = True
        return None


def _tidy(sentence: str) -> str:
    """One clean line: no newlines, no wrapping quotes, no runaway length."""
    sentence = " ".join(sentence.split()).strip().strip('"')
    # Models open with "This is a..." / "This appears to be a..." however firmly
    # the prompt asks them not to. The reader knows they are reading a document.
    sentence = re.sub(
        r"^(this|it|the)\s+(document\s+)?(is|appears to be|seems to be)\s+(a|an|the)?\s*",
        "", sentence, flags=re.I,
    )
    # One sentence was asked for; models often give two, and cutting the second
    # one mid-word reads as a bug. The \w{3,} guard keeps "St. Joseph" and
    # "No. 12" whole - an abbreviation's dot is not the end of a sentence.
    first = re.search(r"\w{3,}[.!?](?=\s)", sentence)
    if first:
        sentence = sentence[: first.end()]
    if len(sentence) > MAX_CHARS:
        sentence = sentence[:MAX_CHARS].rsplit(" ", 1)[0] + "…"
    return sentence[:1].upper() + sentence[1:] if sentence else ""


# OCR of a blurred photo returns rubble - "Lv ik: oi 7 EY m4 mo 72 26 aN LIF".
# Mean word length separates it cleanly from real text: measured across this
# corpus, junk scores 2.25 while every genuine opening, letterheads in caps
# included, scores 4.32 to 6.94. Below this we say nothing rather than quote
# gibberish at someone.
MIN_MEAN_WORD = 3.5


def looks_like_prose(line: str) -> bool:
    words = re.findall(r"[A-Za-z]+", line)
    if not words:
        return False
    return sum(len(w) for w in words) / len(words) >= MIN_MEAN_WORD


def _opening(text: str) -> str:
    """The document's own first sentence - the no-model fallback.

    Notices and invoices lead with their subject, so this is usually the right
    line even without a model reading it. Returns "" when the text is too
    garbled to quote.
    """
    flat = " ".join(text.split())
    if not flat:
        return ""
    end = re.search(r"[.!?]\s", flat[: MAX_CHARS + 40])
    line = _tidy(flat[: end.end()] if end else flat)
    return line if looks_like_prose(line) else ""


def summarize(text: str) -> str:
    """One sentence describing a document. Never raises, may be empty."""
    if not text.strip():
        return ""
    if MODEL:
        written = _generate(text)
        if written:
            return _tidy(written)
    return _opening(text)


def refresh(
    document_ids: list[int] | None = None, redo: bool = False, limit: int = 20
) -> list[tuple[str, str, float]]:
    """Write summaries and report (filename, summary, seconds) for each.

    The digest fills these in as it goes; this exists to run them on demand -
    to backfill after pulling a model, and to see what the model actually says
    before it goes out to anybody.
    """
    where = "extracted_text <> ''"
    params: list = []
    if document_ids:
        where += " AND id = ANY(%s)"
        params.append(document_ids)
    if not redo:
        where += " AND summary = ''"

    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT id, filename, extracted_text FROM documents WHERE {where}"
            " ORDER BY id DESC LIMIT %s",
            (*params, limit),
        ).fetchall()

    done = []
    for doc_id, filename, text in rows:
        started = time.perf_counter()
        summary = summarize(text)
        elapsed = time.perf_counter() - started
        if summary:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE documents SET summary = %s WHERE id = %s", (summary, doc_id)
                )
        done.append((filename, summary, elapsed))
    return done


def for_document(conn: psycopg.Connection, document_id: int) -> str:
    """Cached summary, generated on first use.

    Stored on the document, not per user: it describes the bytes, and identical
    bytes are one document here no matter who received them.
    """
    row = conn.execute(
        "SELECT summary, extracted_text FROM documents WHERE id = %s", (document_id,)
    ).fetchone()
    if row is None:
        return ""
    if row[0]:
        return row[0]
    summary = summarize(row[1] or "")
    if summary:
        conn.execute("UPDATE documents SET summary = %s WHERE id = %s", (summary, document_id))
    return summary
