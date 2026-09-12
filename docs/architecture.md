# Architecture

```
   your WhatsApp numbers                    browser
        |  (Baileys)                           |
        v                                      v
 +------------------+              +------------------------+
 |  bridge/ (Node)  |  webhooks    |  web/ (React, shadcn)  |
 |  N sessions,     |------------->|  chat UI + linking     |
 |  one per number  |              +-----------+------------+
 +------------------+                          | /api
        |                                      v
        |                        +-----------------------------+
        +----------------------->|  FastAPI (wadr.api.app)     |
                                 +--------------+--------------+
                                                v
        ingest: extract -> dedupe (SHA-256) -> chunk -> embed
        search: BM25 + dense vectors, fused by RRF, recency-nudged
                                                v
                                   PostgreSQL 16 + pgvector
```

## Tenancy

Identical bytes are stored once, but *visibility* is per sighting: a document
is yours because one of **your** numbers received it. Search, download and
more-like-this are all scoped in `retrieval/service.py`, in one place, so no
caller can forget to.

## Who sees what in a group chat

Your linked number sits in group chats full of other people, and any of them
can type `/find`. Only you, meaning messages from your own WhatsApp, search
everything that number ever received. For anyone else the search is narrowed to
what they could already see: files shared in the chat they are asking in, and
files they sent themselves. `/get` re-checks the same rule at send time, so a
result nobody was allowed to find cannot be downloaded either.

## Why some results say "loose match"

A result marked "loose match" means nothing actually matched. Semantic search
always returns its nearest neighbours, so rather than pretend, the app shows
them as guesses. Measured on this embedder a correct match can score 0.438
while pure noise scores 0.454, so the two genuinely overlap and a score
threshold would throw away real answers. Labelling is honest where filtering
would be lossy.

The same signal reaches agents: MCP search results carry `weak: true`, and the
server's instructions tell the model to say so rather than bluff.
