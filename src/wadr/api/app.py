"""Internal HTTP API. Run: uv run uvicorn wadr.api.app:app --reload"""

from dataclasses import asdict

from fastapi import FastAPI, HTTPException

from wadr.adapters.openwa import OpenWAAdapter
from wadr.retrieval import service

app = FastAPI(title="WADR")


@app.get("/search")
def search(q: str, model: str = "hybrid", top_k: int = 5):
    """Same engine call the CLI makes - proof the engine is adapter-agnostic."""
    try:
        return [asdict(r) for r in service.search(q, model=model, top_k=top_k)]
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except NotImplementedError as e:
        raise HTTPException(501, str(e)) from e


@app.post("/webhook/openwa")
def openwa_webhook(payload: dict):
    """Inbound document from the bridge - payload contract in wadr/adapters/openwa.py."""
    try:
        return OpenWAAdapter().handle_webhook(payload)
    except (KeyError, ValueError) as e:  # missing field, bad base64, bad timestamp
        raise HTTPException(400, f"bad payload: {e!r}") from e


@app.post("/webhook/openwa/query")
def openwa_query(payload: dict):
    """'/find <query>' from a chat: search, reply into the same chat via bridge /send."""
    query = payload.get("text", "").removeprefix("/find").strip()
    if not query or "chat_id" not in payload:
        raise HTTPException(400, "need chat_id and text '/find <query>'")
    OpenWAAdapter().send_results(payload["chat_id"], service.search(query))
    return {}


@app.get("/similar/{document_id}")
def similar(document_id: int):
    """TODO(WS4): more-like-this via pgvector distance to the doc's chunks (exclude itself)."""
    raise HTTPException(501, "TODO(WS4): /similar endpoint")


@app.post("/feedback")
def feedback():
    """TODO(WS4): insert {query_text, document_id, action} into the feedback table."""
    raise HTTPException(501, "TODO(WS4): feedback logging")
