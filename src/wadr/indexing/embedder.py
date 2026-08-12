"""Ollama embedding client (nomic-embed-text, 768 dims).

ponytail: urllib instead of an HTTP client dep - it's one JSON POST.
"""

import json
import logging
import os
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

# 127.0.0.1, NOT localhost: localhost resolves to ::1 first, Ollama binds IPv4
# only, and urllib has no Happy Eyeballs - it blocks ~2s on the dead IPv6
# connection before falling back. That was 2.3s on every embed, i.e. on every
# ingest and every /find. Measured: 2.24s -> 0.18s.
OLLAMA_URL = os.environ.get("WADR_OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = "nomic-embed-text"
EMBEDDING_DIM = 768  # must match vector(768) in schema.sql

_warned = False


def embed(texts: list[str]) -> list[list[float]] | None:
    """Batch-embed texts. Returns None when Ollama is unreachable - callers
    degrade gracefully to BM25-only (chunks keep NULL embeddings)."""
    global _warned
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/embed",
        data=json.dumps({"model": MODEL, "input": texts}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.load(resp)["embeddings"]
    except (urllib.error.URLError, TimeoutError, KeyError) as e:
        if not _warned:
            log.warning(
                "Ollama unreachable at %s (%s) - dense search disabled, BM25 only. "
                "Fix: install Ollama and `ollama pull %s`.",
                OLLAMA_URL, e, MODEL,
            )
            _warned = True
        return None


def embed_query(query: str) -> list[float] | None:
    vecs = embed([query])
    return vecs[0] if vecs else None
