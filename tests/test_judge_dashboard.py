"""The /judge relevance-judging dashboard.

Uses a throwaway judgments file so a test run never touches
evaluation/queries.jsonl. Needs a live DB, like the other integration tests.
"""

import json

import pytest
from fastapi.testclient import TestClient

from wadr.api.app import app
from wadr.evaluation import run_eval


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = tmp_path / "queries.jsonl"
    path.write_text(
        json.dumps({"qid": "q01", "query": "exam timetable", "relevant": {}}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(run_eval, "DEFAULT_QUERIES", path)
    return TestClient(app), path


def test_page_serves(client):
    api, _ = client
    r = api.get("/judge")
    assert r.status_code == 200
    assert "WADR relevance judging" in r.text


def test_pool_unions_every_model(client):
    api, _ = client
    r = api.get("/judge/api/pool/q01")
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "exam timetable"
    # candidates carry which models found them - that is the point of pooling
    for c in body["candidates"]:
        assert set(c["found_by"]) <= set(run_eval.MODELS)
        assert c["grade"] == 0
    assert api.get("/judge/api/pool/nope").status_code == 404


def test_grading_round_trips_to_the_file(client):
    api, path = client
    candidates = api.get("/judge/api/pool/q01").json()["candidates"]
    if not candidates:
        pytest.skip("no documents ingested to grade")
    file_hash = candidates[0]["file_hash"]

    assert api.post("/judge/api/grade",
                    json={"qid": "q01", "file_hash": file_hash, "grade": 3}).json()["graded"] == 1
    stored = json.loads([ln for ln in path.read_text(encoding="utf-8").splitlines()
                         if ln.startswith("{")][0])
    assert stored["relevant"] == {file_hash: 3}

    # grade 0 means "not relevant", which is recorded as absence, not a 0 entry
    assert api.post("/judge/api/grade",
                    json={"qid": "q01", "file_hash": file_hash, "grade": 0}).json()["graded"] == 0

    # a graded-then-no-longer-retrieved document must stay visible and editable
    api.post("/judge/api/grade", json={"qid": "q01", "file_hash": "deadbeef", "grade": 2})
    hashes = [c["file_hash"] for c in api.get("/judge/api/pool/q01").json()["candidates"]]
    assert "deadbeef" in hashes


def test_grade_rejects_bad_input(client):
    api, _ = client

    def post(payload):
        return api.post("/judge/api/grade", json=payload).status_code

    assert post({"qid": "q01", "file_hash": "h", "grade": 9}) == 400    # out of range
    assert post({"qid": "q01", "file_hash": "h", "grade": "x"}) == 400  # not a number
    assert post({"qid": "q01"}) == 400                                 # missing keys
    assert post({"qid": "zz", "file_hash": "h", "grade": 1}) == 404     # unknown query


def test_queries_can_be_added_and_deleted(client):
    api, _ = client
    added = api.post("/judge/api/queries", json={"query": "biryani"})
    assert added.status_code == 200 and added.json()["qid"] == "q02"
    assert api.post("/judge/api/queries", json={"query": "biryani"}).status_code == 409
    assert api.post("/judge/api/queries", json={"query": "  "}).status_code == 400
    assert len(api.get("/judge/api/queries").json()) == 2

    assert api.delete("/judge/api/queries/q02").status_code == 200
    assert [q["qid"] for q in api.get("/judge/api/queries").json()] == ["q01"]


def test_benchmark_refuses_ungraded_judgments(client):
    api, _ = client
    # nothing graded yet: better a clear 400 than a table of zeros that reads
    # as "every model failed"
    assert api.get("/judge/api/benchmark").status_code == 400
