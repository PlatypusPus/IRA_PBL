"""API keys and the MCP tools an agent calls.

The tools are exercised as plain functions with WADR_API_KEY set; the stdio
protocol itself is the SDK's job, not ours.
"""

import base64
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

import wadr.api.app as appmod
from wadr import accounts
from wadr.db import get_conn
from wadr.mcp_server import find_similar, read_document, recent_documents, search_documents


@pytest.fixture
def agent(monkeypatch):
    """One account with one document, and WADR_API_KEY set to its key."""
    monkeypatch.setattr(appmod, "BRIDGE_TOKEN", "test-token")
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    email = f"mcp-{stamp}@test.invalid"

    client = TestClient(appmod.app)
    client.post("/api/auth/signup", json={"email": email, "password": "hunter2hunter2"})
    user = accounts.user_for_token(client.cookies["wadr_session"])
    account = accounts.create_account(user["id"], "phone")
    key = accounts.create_api_key(user["id"], "test key")
    monkeypatch.setenv("WADR_API_KEY", key)

    body = f"Invoice INV-2291 from Nimbus Systems, 48500 rupees due 2026-09-30. {stamp}"
    filename = f"mcp-invoice-{stamp}.txt"
    res = TestClient(appmod.app).post(
        "/api/bridge/document",
        headers={"X-Bridge-Token": "test-token"},
        json={
            "session_key": account["session_key"], "chat_id": "g@us", "sender": "dad",
            "timestamp": datetime.now(UTC).isoformat(), "filename": filename,
            "mime_type": "text/plain",
            "data_base64": base64.b64encode(body.encode()).decode(),
        },
    )
    assert res.status_code == 200

    yield {"user": user, "key": key, "document_id": res.json()["document_id"],
           "filename": filename, "stamp": stamp}

    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE email = %s", (email,))
        conn.execute("DELETE FROM documents WHERE filename = %s", (filename,))


def test_search_returns_document_ids_to_read(agent):
    out = search_documents(f"invoice {agent['stamp']}")
    assert out["results"], "the seeded invoice should be found"
    hit = out["results"][0]
    assert hit["document_id"] == agent["document_id"]
    assert hit["weak"] is False
    assert hit["sender"] == "dad"


def test_search_honours_inline_filters(agent):
    assert search_documents(f"invoice {agent['stamp']} from:dad")["results"]
    assert search_documents(f"invoice {agent['stamp']} from:nobody")["results"] == []


def test_search_reports_a_bad_filter_instead_of_raising(agent):
    out = search_documents("invoice before:soon")
    assert "ISO date" in out["error"]
    assert out["results"] == []


def test_read_document_returns_text_an_agent_can_answer_from(agent):
    out = read_document(agent["document_id"])
    assert "INV-2291" in out["text"]
    assert out["truncated"] is False


def test_tools_refuse_documents_from_other_accounts(agent):
    assert "error" in read_document(999_999_999)
    assert "error" in find_similar(999_999_999)


def test_recent_documents_lists_the_seeded_file(agent):
    names = [d["filename"] for d in recent_documents(limit=50)["results"]]
    assert agent["filename"] in names


def test_a_revoked_key_stops_working_at_once(agent):
    key_id = accounts.list_api_keys(agent["user"]["id"])[0]["id"]
    accounts.revoke_api_key(agent["user"]["id"], key_id)
    with pytest.raises(ValueError, match="WADR_API_KEY"):
        search_documents("anything")


def test_keys_are_stored_hashed_not_in_plaintext(agent):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT key_hash, prefix FROM api_keys WHERE user_id = %s",
            (agent["user"]["id"],),
        ).fetchone()
    # a database dump must not hand over working credentials
    assert agent["key"] not in row[0]
    assert row[1] == agent["key"][:12]


def test_key_routes_require_a_session():
    anon = TestClient(appmod.app)
    assert anon.get("/api/keys").status_code == 401
    assert anon.post("/api/keys", json={}).status_code == 401
