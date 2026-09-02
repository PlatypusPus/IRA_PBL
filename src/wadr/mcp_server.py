"""MCP server: hand an agent your WhatsApp document archive.

Run it over stdio and point Claude (Desktop, Code, or anything speaking MCP)
at it:

    WADR_API_KEY=wadr_... uv run wadr mcp

Claude Desktop / Claude Code config:

    {
      "mcpServers": {
        "wadr": {
          "command": "uv",
          "args": ["run", "--directory", "/path/to/IRPBL", "wadr", "mcp"],
          "env": { "WADR_API_KEY": "wadr_..." }
        }
      }
    }

The key identifies exactly one account, so every tool here is already scoped -
an agent can only ever reach documents that account's own numbers received.
Create a key in the web app under API keys.

Why these four tools: search finds candidates, read_document is what makes the
archive *useful* (the agent can answer from the contents, not just hand back
filenames), recent_documents answers "what came in this week", and
find_similar covers "more like this one" without another search.
"""

import logging
import os
import sys

from mcp.server.mcpserver import MCPServer

from wadr import accounts
from wadr.retrieval import service

log = logging.getLogger(__name__)

# Tools return plain dicts, so results arrive as a JSON text block rather
# than MCP structured_content. structured_output=True needs a TypedDict or
# Pydantic model per return type; the text block is what clients read
# anyway, so that is four schemas for no behaviour change.

server = MCPServer(
    "wadr",
    instructions=(
        "Search and read the documents that arrived on this user's linked "
        "WhatsApp numbers - PDFs, photographed pages (OCR'd), voice notes "
        "(transcribed), and office files.\n\n"
        "Start with search_documents. Its results carry document_id values; "
        "pass one to read_document to get the actual text and answer from it "
        "rather than guessing from the filename.\n\n"
        "Queries accept filters inline: from:<sender> in:<chat> type:<pdf|txt|"
        "docx|png> before:<YYYY-MM-DD> after:<YYYY-MM-DD>. For example "
        "'invoice from:dad type:pdf after:2026-01-01'.\n\n"
        "A result flagged weak=true means nothing actually matched and this is "
        "only the nearest neighbour - say so rather than presenting it as the "
        "answer."
    ),
)


def _user() -> dict:
    """Resolve the API key once per call, so a revoked key stops working
    immediately rather than at the next restart."""
    user = accounts.user_for_api_key(os.environ.get("WADR_API_KEY"))
    if user is None:
        raise ValueError(
            "WADR_API_KEY is missing or invalid. Create a key in the WADR web "
            "app (API keys) and set it in this server's environment."
        )
    return user


@server.tool(
    title="Search documents",
    description=(
        "Search the user's WhatsApp documents by meaning and by keyword. "
        "Supports inline filters: from:, in:, type:, before:, after:. "
        "Returns document_id values to pass to read_document."
    ),
)
def search_documents(query: str, limit: int = 5) -> dict:
    user = _user()
    try:
        hits = service.search(query, user["id"], top_k=max(1, min(limit, 20)))
    except ValueError as e:  # malformed filter token, e.g. before:soon
        return {"error": str(e), "results": []}

    if not hits:
        return {
            "results": [],
            "note": "Nothing matched. The user may have no numbers linked yet, "
                    "or the document was never shared with a linked number.",
        }
    return {
        "results": [
            {
                "document_id": h.document_id,
                "filename": h.filename,
                "excerpt": h.snippet.replace("*", ""),
                "sender": h.sender,
                "received_at": h.sent_at.isoformat() if h.sent_at else None,
                "weak": h.weak,
            }
            for h in hits
        ],
        "note": (
            "No document actually matched; these are the nearest neighbours. "
            "Tell the user nothing matched."
            if all(h.weak for h in hits)
            else None
        ),
    }


@server.tool(
    title="Read a document",
    description=(
        "Full extracted text of one document, so you can answer from its "
        "contents. Works for PDFs, OCR'd images and transcribed voice notes."
    ),
)
def read_document(document_id: int) -> dict:
    user = _user()
    found = service.get_document_text(document_id, user["id"])
    if found is None:
        return {"error": f"No document {document_id} in this account."}
    if not found["text"].strip():
        found["note"] = (
            "This document has no extracted text - it may be a scan that failed "
            "OCR, or was ingested before OCR was available. Re-sharing it on "
            "WhatsApp re-runs extraction."
        )
    return found


@server.tool(
    title="Recent documents",
    description="Most recently received documents, newest first.",
)
def recent_documents(limit: int = 20) -> dict:
    user = _user()
    return {"results": service.recent_documents(user["id"], max(1, min(limit, 50)))}


@server.tool(
    title="Find similar documents",
    description="Documents closest in meaning to a given one - 'more like this'.",
)
def find_similar(document_id: int, limit: int = 5) -> dict:
    user = _user()
    try:
        hits = service.similar(document_id, user["id"], top_k=max(1, min(limit, 20)))
    except LookupError:
        return {"error": f"No document {document_id} in this account."}
    return {
        "results": [
            {
                "document_id": h.document_id,
                "filename": h.filename,
                "excerpt": h.snippet,
                "similarity": round(h.score, 3),
            }
            for h in hits
        ]
    }


def main() -> None:
    # stdout is the MCP transport: anything else printed there corrupts the
    # protocol stream, so logging goes to stderr.
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
