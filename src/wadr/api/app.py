"""Product HTTP API.

Run: uv run uvicorn wadr.api.app:app --reload

Everything under /api/* except signup and login requires a session cookie.
The bridge authenticates with a shared secret instead (WADR_BRIDGE_TOKEN) and
says which linked number a message arrived on via its session_key.
"""

import io
import os
from dataclasses import asdict
from pathlib import Path

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from wadr import accounts
from wadr.api import bridge_client
from wadr.chat import NotYours, answer, conversations, history, start
from wadr.chat import delete as delete_conversation
from wadr.retrieval import service

app = FastAPI(title="WADR")

SESSION_COOKIE = "wadr_session"
# The bridge is a trusted internal process, not a user. Empty means "no bridge
# may call in", which is the safe default if the operator forgets to set it.
BRIDGE_TOKEN = os.environ.get("WADR_BRIDGE_TOKEN", "")


def current_user(wadr_session: str | None = Cookie(default=None)) -> dict:
    user = accounts.user_for_token(wadr_session)
    if user is None:
        raise HTTPException(401, "not signed in")
    return user


def require_bridge(x_bridge_token: str | None = Header(default=None)) -> None:
    if not BRIDGE_TOKEN or x_bridge_token != BRIDGE_TOKEN:
        raise HTTPException(401, "bad bridge token")


# ----------------------------------------------------------------- auth


def _set_session(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE, token,
        httponly=True,   # JavaScript must never be able to read the session token
        samesite="lax",  # blocks the cross-site form-post CSRF shape
        max_age=accounts.SESSION_DAYS * 86400,
        path="/",
    )


@app.post("/api/auth/signup")
def signup(payload: dict, response: Response) -> dict:
    try:
        accounts.sign_up(payload.get("email", ""), payload.get("password", ""))
        token = accounts.log_in(payload["email"], payload["password"])
    except accounts.AuthError as e:
        raise HTTPException(400, str(e)) from e
    _set_session(response, token)
    return accounts.user_for_token(token)


@app.post("/api/auth/login")
def login(payload: dict, response: Response) -> dict:
    try:
        token = accounts.log_in(payload.get("email", ""), payload.get("password", ""))
    except accounts.AuthError as e:
        raise HTTPException(401, str(e)) from e
    _set_session(response, token)
    return accounts.user_for_token(token)


@app.post("/api/auth/logout")
def logout(response: Response, wadr_session: str | None = Cookie(default=None)) -> dict:
    accounts.log_out(wadr_session)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)) -> dict:
    return user


# -------------------------------------------------------- linked numbers


def _own_account(user: dict, account_id: int) -> dict:
    for account in accounts.list_accounts(user["id"]):
        if account["id"] == account_id:
            return account
    raise HTTPException(404, "no such linked number")


@app.get("/api/accounts")
def get_accounts(user: dict = Depends(current_user)) -> list[dict]:
    return accounts.list_accounts(user["id"])


@app.post("/api/accounts")
def add_account(payload: dict, user: dict = Depends(current_user)) -> dict:
    account = accounts.create_account(user["id"], payload.get("label", ""))
    bridge_client.start_session(account["session_key"])
    return account


@app.get("/api/accounts/{account_id}/qr")
def account_qr(account_id: int, user: dict = Depends(current_user)) -> dict:
    """Poll while linking: {status, qr, pairing_code, phone}."""
    return bridge_client.session_status(_own_account(user, account_id)["session_key"])


@app.post("/api/accounts/{account_id}/pair")
def account_pair(account_id: int, payload: dict, user: dict = Depends(current_user)) -> dict:
    """Pairing code instead of a QR - iPhones scan screen QRs badly."""
    key = _own_account(user, account_id)["session_key"]
    return bridge_client.pairing_code(key, payload.get("phone", ""))


@app.delete("/api/accounts/{account_id}")
def remove_account(account_id: int, user: dict = Depends(current_user)) -> dict:
    try:
        session_key = accounts.delete_account(user["id"], account_id)
    except accounts.AuthError as e:
        raise HTTPException(404, str(e)) from e
    bridge_client.stop_session(session_key)
    return {"ok": True}


# --------------------------------------------------------------- API keys


@app.get("/api/keys")
def get_keys(user: dict = Depends(current_user)) -> list[dict]:
    return accounts.list_api_keys(user["id"])


@app.post("/api/keys")
def add_key(payload: dict, user: dict = Depends(current_user)) -> dict:
    """Mint a key. The plaintext is in this response and nowhere else, ever."""
    key = accounts.create_api_key(user["id"], payload.get("label", ""))
    return {"key": key, "keys": accounts.list_api_keys(user["id"])}


@app.delete("/api/keys/{key_id}")
def remove_key(key_id: int, user: dict = Depends(current_user)) -> dict:
    try:
        accounts.revoke_api_key(user["id"], key_id)
    except accounts.AuthError as e:
        raise HTTPException(404, str(e)) from e
    return {"ok": True}


# ------------------------------------------------------------------ chat


@app.get("/api/conversations")
def get_conversations(user: dict = Depends(current_user)) -> list[dict]:
    return conversations(user["id"])


@app.post("/api/conversations")
def new_conversation(user: dict = Depends(current_user)) -> dict:
    return start(user["id"])


@app.delete("/api/conversations/{conversation_id}")
def drop_conversation(conversation_id: int, user: dict = Depends(current_user)) -> dict:
    try:
        delete_conversation(user["id"], conversation_id)
    except NotYours as e:
        raise HTTPException(404, str(e)) from e
    return {"ok": True}


@app.get("/api/chat")
def get_history(conversation_id: int, user: dict = Depends(current_user)) -> list[dict]:
    try:
        return history(user["id"], conversation_id)
    except NotYours as e:
        raise HTTPException(404, str(e)) from e


@app.post("/api/chat")
def post_message(payload: dict, user: dict = Depends(current_user)) -> dict:
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "say something")
    try:
        return answer(user["id"], text, payload.get("conversation_id"))
    except NotYours as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:  # malformed filter token, e.g. before:soon
        raise HTTPException(400, str(e)) from e


@app.get("/api/documents/{document_id}/similar")
def similar(document_id: int, user: dict = Depends(current_user)) -> list[dict]:
    try:
        return [asdict(r) for r in service.similar(document_id, user["id"])]
    except LookupError as e:
        raise HTTPException(404, str(e)) from e


@app.get("/api/documents/{document_id}/file")
def download(document_id: int, inline: bool = False, user: dict = Depends(current_user)):
    """The file itself. inline=1 for previewing it in the page instead of saving.

    A PDF in an <iframe> is downloaded rather than rendered unless the
    disposition says inline, so the caller has to ask for it.
    """
    found = service.get_document(document_id, user["id"])
    if found is None:
        raise HTTPException(404, "not found, or not stored - re-share it on WhatsApp")
    filename, mime_type, content = found
    return StreamingResponse(
        io.BytesIO(content),
        media_type=mime_type,
        headers={
            "Content-Disposition":
                f'{"inline" if inline else "attachment"}; filename="{filename}"',
            # These bytes never change - the id is a content hash's document.
            "Cache-Control": "private, max-age=3600",
        },
    )


# ---------------------------------------------------------------- bridge


@app.post("/api/bridge/document", dependencies=[Depends(require_bridge)])
def bridge_document(payload: dict) -> dict:
    """A file arrived on one of the linked numbers."""
    from wadr.adapters.openwa import OpenWAAdapter

    try:
        return OpenWAAdapter().handle_webhook(payload)
    except (KeyError, ValueError) as e:
        raise HTTPException(400, f"bad payload: {e!r}") from e


@app.post("/api/bridge/status", dependencies=[Depends(require_bridge)])
def bridge_status(payload: dict) -> dict:
    """The bridge reporting that a session went linked or logged out."""
    session_key = payload.get("session_key")
    if not session_key:
        raise HTTPException(400, "need session_key")
    accounts.mark_linked(session_key, payload.get("phone"), payload.get("status", "pending"))
    return {"ok": True}


@app.post("/api/bridge/query", dependencies=[Depends(require_bridge)])
def bridge_query(payload: dict) -> dict:
    """A '/find ...' message typed in WhatsApp itself."""
    from wadr.adapters.openwa import OpenWAAdapter

    OpenWAAdapter().handle_query(payload)
    return {}


@app.post("/api/bridge/get", dependencies=[Depends(require_bridge)])
def bridge_get(payload: dict) -> dict:
    from wadr.adapters.openwa import OpenWAAdapter

    OpenWAAdapter().handle_get(payload)
    return {}


# ------------------------------------------------------------------- web

# The built React app, if it has been built. Mounted last so it never shadows
# /api/*; unknown paths fall through to index.html for client-side routing.
WEB_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"

if (WEB_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        return FileResponse(WEB_DIST / "index.html")

else:
    @app.get("/")
    def no_build() -> dict:
        return {
            "detail": "web UI not built - run: cd web && npm install && npm run build",
            "api_docs": "/docs",
        }
