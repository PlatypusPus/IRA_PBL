"""Tenancy is the security boundary of this product: a document must be
reachable only by the account whose linked number received it.

These run against a live database and clean up after themselves.
"""

import base64
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

import wadr.api.app as appmod
from wadr import accounts
from wadr.db import get_conn
from wadr.indexing import embedder

BRIDGE = {"X-Bridge-Token": "test-token"}


@pytest.fixture
def world(monkeypatch):
    """Two users, one linked number each, one private document each."""
    monkeypatch.setattr(appmod, "BRIDGE_TOKEN", "test-token")
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    emails = [f"alice-{stamp}@test.invalid", f"bob-{stamp}@test.invalid"]
    clients, users, accts = [], [], []

    for email in emails:
        client = TestClient(appmod.app)
        assert client.post(
            "/api/auth/signup", json={"email": email, "password": "hunter2hunter2"}
        ).status_code == 200
        user = accounts.user_for_token(client.cookies["wadr_session"])
        clients.append(client)
        users.append(user)
        accts.append(accounts.create_account(user["id"], "phone"))

    anon = TestClient(appmod.app)
    docs = []
    for i, account in enumerate(accts):
        text = f"{'alice merger dossier' if i == 0 else 'bob badminton roster'} {stamp}"
        res = anon.post("/api/bridge/document", headers=BRIDGE, json={
            "session_key": account["session_key"], "chat_id": "g@us", "sender": "someone",
            "timestamp": datetime.now(UTC).isoformat(), "filename": f"tenancy-{i}-{stamp}.txt",
            "mime_type": "text/plain",
            "data_base64": base64.b64encode(text.encode()).decode(),
        })
        assert res.status_code == 200
        docs.append(res.json()["document_id"])

    yield {"clients": clients, "docs": docs, "stamp": stamp}

    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE email = ANY(%s)", (emails,))
        conn.execute("DELETE FROM documents WHERE id = ANY(%s)", (docs,))


def test_search_never_crosses_accounts(world):
    alice, bob = world["clients"]
    reply = bob.post("/api/chat", json={"text": "merger dossier"}).json()
    assert all("tenancy-0" not in hit["filename"] for hit in reply["results"])

    reply = alice.post("/api/chat", json={"text": "merger dossier"}).json()
    assert any("tenancy-0" in hit["filename"] for hit in reply["results"])


def test_download_and_similar_are_scoped(world):
    alice, bob = world["clients"]
    alice_doc = world["docs"][0]
    assert alice.get(f"/api/documents/{alice_doc}/file").status_code == 200
    # 404 rather than 403: whether someone else's document exists is not
    # information Bob is entitled to.
    assert bob.get(f"/api/documents/{alice_doc}/file").status_code == 404
    assert bob.get(f"/api/documents/{alice_doc}/similar").status_code == 404


def test_a_miss_is_reported_as_a_guess_not_a_match(world):
    """Dense retrieval always returns its nearest k; the reply must not call
    that a match."""
    if embedder.embed(["ping"]) is None:
        # Without an embedder there are no nearest neighbours to mislabel, and
        # "Nothing matched" is the correct answer - a different test's subject.
        pytest.skip("needs Ollama: this is about dense retrieval's guesses")
    _, bob = world["clients"]
    reply = bob.post("/api/chat", json={"text": "merger dossier"}).json()
    assert "closest" in reply["text"].lower()
    assert all(hit["weak"] for hit in reply["results"])


def test_everything_requires_a_session(world):
    anon = TestClient(appmod.app)
    for method, path in [
        ("get", "/api/chat"), ("post", "/api/chat"), ("get", "/api/accounts"),
        ("get", f"/api/documents/{world['docs'][0]}/file"),
    ]:
        kwargs = {"json": {"text": "x"}} if method == "post" else {}
        assert getattr(anon, method)(path, **kwargs).status_code == 401, path


def test_bridge_routes_need_the_shared_secret(world):
    anon = TestClient(appmod.app)
    assert anon.post("/api/bridge/document", json={}).status_code == 401
    assert anon.post(
        "/api/bridge/document", headers={"X-Bridge-Token": "wrong"}, json={}
    ).status_code == 401


def test_unlinking_a_number_hides_its_documents(world):
    alice, _ = world["clients"]
    account_id = alice.get("/api/accounts").json()[0]["id"]
    assert alice.delete(f"/api/accounts/{account_id}").status_code == 200
    reply = alice.post("/api/chat", json={"text": "merger dossier"}).json()
    assert reply["results"] == []
