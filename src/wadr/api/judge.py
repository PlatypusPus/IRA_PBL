"""Relevance-judging dashboard: /judge

Judgments must come from a person looking at real results, so this serves a
small page that does exactly that. For each query it POOLS the top results of
all five models - the union, not one model's list - because grading only what
(say) BM25 returns would bake that model's blind spots into the gold data and
flatter it at evaluation time. Pooling is how TREC builds its judgments, and
the report should say so.

Grades are written straight back to evaluation/queries.jsonl, so this page and
hand-editing that file are interchangeable.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from wadr.api.judge_page import PAGE
from wadr.db import get_conn
from wadr.evaluation import judgments, run_eval
from wadr.retrieval import service

router = APIRouter()

POOL_DEPTH = 10  # per model, before the union


def _path() -> Path:
    return run_eval.DEFAULT_QUERIES


def _load() -> list[dict]:
    path = _path()
    if not path.exists():
        raise HTTPException(404, f"no judgments file at {path}")
    return judgments.load(path)


def _find(rows: list[dict], qid: str) -> dict:
    for row in rows:
        if row["qid"] == qid:
            return row
    raise HTTPException(404, f"no query {qid!r}")


@router.get("/judge", response_class=HTMLResponse)
def page() -> str:
    return PAGE


@router.get("/judge/api/queries")
def list_queries() -> list[dict]:
    return [
        {"qid": r["qid"], "query": r["query"], "graded": len(r["relevant"])}
        for r in _load()
    ]


@router.post("/judge/api/queries")
def add_query(payload: dict) -> dict:
    text = (payload.get("query") or "").strip()
    if not text:
        raise HTTPException(400, "query must not be empty")
    rows = _load()
    if any(r["query"] == text for r in rows):
        raise HTTPException(409, "that query already exists")
    used = {r["qid"] for r in rows}
    qid = next(f"q{n:02d}" for n in range(1, 1000) if f"q{n:02d}" not in used)
    rows.append({"qid": qid, "query": text, "relevant": {}})
    judgments.dump(_path(), rows)
    return {"qid": qid, "query": text, "graded": 0}


@router.delete("/judge/api/queries/{qid}")
def delete_query(qid: str) -> dict:
    rows = _load()
    _find(rows, qid)
    judgments.dump(_path(), [r for r in rows if r["qid"] != qid])
    return {"deleted": qid}


@router.get("/judge/api/pool/{qid}")
def pool(qid: str) -> dict:
    """Union of every model's top results for this query, with current grades."""
    row = _find(_load(), qid)
    with get_conn() as conn:
        hash_by_id = dict(conn.execute("SELECT id, file_hash FROM documents").fetchall())

    candidates: dict[str, dict] = {}
    for model in run_eval.MODELS:
        try:
            hits = service.search(row["query"], model=model, top_k=POOL_DEPTH)
        except ValueError as e:  # a malformed filter token in the query text
            raise HTTPException(400, str(e)) from e
        for rank, hit in enumerate(hits, start=1):
            file_hash = hash_by_id.get(hit.document_id)
            if file_hash is None:
                continue
            entry = candidates.setdefault(
                file_hash,
                {
                    "file_hash": file_hash,
                    "filename": hit.filename,
                    "snippet": hit.snippet,
                    "found_by": [],
                    "best_rank": rank,
                },
            )
            entry["found_by"].append(model)
            entry["best_rank"] = min(entry["best_rank"], rank)

    # Documents already graded but no longer retrieved still need to be shown,
    # otherwise a grade becomes invisible and un-editable.
    for file_hash in row["relevant"]:
        if file_hash not in candidates:
            with get_conn() as conn:
                found = conn.execute(
                    "SELECT filename, left(extracted_text, 200) FROM documents"
                    " WHERE file_hash = %s",
                    (file_hash,),
                ).fetchone()
            candidates[file_hash] = {
                "file_hash": file_hash,
                "filename": found[0] if found else "(no longer in the corpus)",
                "snippet": (found[1] if found else "") or "",
                "found_by": [],
                "best_rank": 999,
            }

    ordered = sorted(candidates.values(), key=lambda c: (c["best_rank"], c["filename"]))
    for c in ordered:
        c["grade"] = row["relevant"].get(c["file_hash"], 0)
    return {"qid": qid, "query": row["query"], "candidates": ordered}


@router.post("/judge/api/grade")
def grade(payload: dict) -> dict:
    missing = {"qid", "file_hash", "grade"} - set(payload)
    if missing:
        raise HTTPException(400, f"missing key(s): {', '.join(sorted(missing))}")
    try:
        value = int(payload["grade"])
    except (TypeError, ValueError) as e:
        raise HTTPException(400, f"grade must be an integer, got {payload['grade']!r}") from e
    if not 0 <= value <= 3:
        raise HTTPException(400, "grade must be 0..3")

    rows = _load()
    row = _find(rows, payload["qid"])
    if value == 0:
        row["relevant"].pop(payload["file_hash"], None)  # 0 means "not relevant" = absent
    else:
        row["relevant"][payload["file_hash"]] = value
    judgments.dump(_path(), rows)
    return {"qid": row["qid"], "graded": len(row["relevant"])}


@router.get("/judge/api/benchmark")
def benchmark() -> dict:
    all_rows = judgments.load(_path())
    rows = [r for r in all_rows if r["relevant"]]
    if not rows:
        raise HTTPException(400, "nothing graded yet - grade at least one query first")
    with get_conn() as conn:
        hash_by_id = dict(conn.execute("SELECT id, file_hash FROM documents").fetchall())
    return {
        "graded": len(rows),
        "total": len(all_rows),
        "columns": ["P@5", "R@5", "F1@5", "MRR", "nDCG@10"],
        "results": [
            {"model": m, **run_eval.evaluate(m, rows, hash_by_id)} for m in run_eval.MODELS
        ],
    }
