"""Internal HTTP API. Run: uv run uvicorn wadr.api.app:app --reload"""

from dataclasses import asdict

import psycopg
from fastapi import FastAPI, HTTPException

from wadr.adapters.openwa import OpenWAAdapter
from wadr.retrieval import service

app = FastAPI(title="WADR")


@app.get("/health")
def health():
    """Liveness probe for Docker/bridge - also checks DB connectivity."""
    try:
        from wadr.db import get_conn

        with get_conn() as conn:
            conn.execute("SELECT 1")
        return {"status": "ok", "db": "up"}
    except Exception as e:  # noqa: BLE001
        return {"status": "degraded", "db": str(e)}


@app.get("/search")
def search(q: str, model: str = "hybrid", top_k: int = 5):
    """Same engine call the CLI makes - proof the engine is adapter-agnostic."""
    try:
        return [asdict(r) for r in service.search(q, model=model, top_k=top_k)]
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except NotImplementedError as e:
        raise HTTPException(501, str(e)) from e
    except psycopg.OperationalError as e:
        raise HTTPException(503, f"database unavailable: {e}") from e


@app.post("/webhook/openwa")
def openwa_webhook(payload: dict):
    """Inbound document from the bridge - payload contract in wadr/adapters/openwa.py."""
    try:
        return OpenWAAdapter().handle_webhook(payload)
    except (KeyError, ValueError) as e:  # missing field, bad base64, bad timestamp
        raise HTTPException(400, f"bad payload: {e!r}") from e
    except psycopg.OperationalError as e:
        raise HTTPException(503, f"database unavailable: {e}") from e


@app.post("/webhook/openwa/query")
def openwa_query(payload: dict):
    """'/find <query>' from a chat: search, reply into the same chat via bridge /send."""
    if "chat_id" not in payload:
        raise HTTPException(400, "need chat_id")
    OpenWAAdapter().handle_query(payload)
    return {}


@app.post("/webhook/openwa/get")
def openwa_get(payload: dict):
    """'/get <n>' from a chat: send the nth file of the last /find via bridge /send-file."""
    if "chat_id" not in payload:
        raise HTTPException(400, "need chat_id")
    OpenWAAdapter().handle_get(payload)
    return {}


@app.get("/similar/{document_id}")
def similar(document_id: int, top_k: int = 5):
    """More-like-this: pgvector neighbours of this document's chunks, itself excluded."""
    try:
        return [asdict(r) for r in service.similar(document_id, top_k=top_k)]
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
    except psycopg.OperationalError as e:
        raise HTTPException(503, f"database unavailable: {e}") from e


@app.post("/feedback")
def feedback(payload: dict):
    """Log a relevance signal: {query_text, document_id, action}.

    action is one of service.FEEDBACK_ACTIONS.
    """
    missing = {"query_text", "document_id", "action"} - set(payload)
    if missing:
        raise HTTPException(400, f"missing key(s): {', '.join(sorted(missing))}")
    try:
        return {"id": service.log_feedback(
            payload["query_text"], int(payload["document_id"]), payload["action"]
        )}
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e)) from e
    except psycopg.OperationalError as e:
        raise HTTPException(503, f"database unavailable: {e}") from e
