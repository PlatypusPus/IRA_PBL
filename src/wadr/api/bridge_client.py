"""Talking to the Node bridge, which owns every WhatsApp session.

One bridge process holds N sessions, one per linked number, each keyed by the
account's session_key. The API asks it to start/stop sessions and polls for
the QR while a user is linking.

The bridge being down must never 500 the product: every call degrades to a
status the UI can render and explain.
"""

import json
import logging
import os
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

# 127.0.0.1, not localhost - see indexing/embedder.py; urllib tries ::1 first
# and stalls seconds waiting for it to fail.
BRIDGE_URL = os.environ.get("WADR_BRIDGE_URL", "http://127.0.0.1:8085")
BRIDGE_TOKEN = os.environ.get("WADR_BRIDGE_TOKEN", "")
TIMEOUT = 15


def _call(method: str, route: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(
        BRIDGE_URL + route,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", "X-Bridge-Token": BRIDGE_TOKEN},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:200]
        log.warning("bridge %s %s -> HTTP %s: %s", method, route, e.code, detail)
        return {"status": "error", "detail": detail}
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        log.warning("bridge unreachable at %s (%s)", BRIDGE_URL, e)
        return {
            "status": "bridge_offline",
            "detail": "The WhatsApp bridge is not running. Start it: cd bridge && npm start",
        }


def start_session(session_key: str) -> dict:
    return _call("POST", "/sessions", {"session_key": session_key})


def stop_session(session_key: str) -> dict:
    return _call("DELETE", f"/sessions/{session_key}")


def session_status(session_key: str) -> dict:
    return _call("GET", f"/sessions/{session_key}")


def pairing_code(session_key: str, phone: str) -> dict:
    return _call("POST", f"/sessions/{session_key}/pair", {"phone": phone})


def send_text(session_key: str, chat_id: str, text: str) -> dict:
    return _call("POST", "/send", {"session_key": session_key, "chat_id": chat_id, "text": text})


def send_file(
    session_key: str, chat_id: str, filename: str, mime_type: str, data_base64: str
) -> dict:
    return _call("POST", "/send-file", {
        "session_key": session_key, "chat_id": chat_id, "filename": filename,
        "mime_type": mime_type, "data_base64": data_base64,
    })
