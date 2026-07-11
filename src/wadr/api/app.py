"""Internal HTTP API. Run: uv run uvicorn wadr.api.app:app --reload"""

from dataclasses import asdict

from fastapi import FastAPI, HTTPException

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
def openwa_webhook():
    """TODO(WS1): validate payload, call OpenWAAdapter().handle_webhook(body).

    Full payload contract documented in wadr/adapters/openwa.py.
    """
    raise HTTPException(501, "TODO(WS1): open-wa webhook - contract in wadr/adapters/openwa.py")


@app.get("/similar/{document_id}")
def similar(document_id: int):
    """TODO(WS4): more-like-this via pgvector distance to the doc's chunks (exclude itself)."""
    raise HTTPException(501, "TODO(WS4): /similar endpoint")


@app.post("/feedback")
def feedback():
    """TODO(WS4): insert {query_text, document_id, action} into the feedback table."""
    raise HTTPException(501, "TODO(WS4): feedback logging")
