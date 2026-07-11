-- 0001: initial WADR schema. Applied by `uv run wadr migrate`.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
    id             BIGSERIAL PRIMARY KEY,
    file_hash      TEXT NOT NULL UNIQUE,   -- SHA-256 hex; content identity for dedupe
    filename       TEXT NOT NULL,          -- first-seen filename
    mime_type      TEXT NOT NULL DEFAULT 'application/octet-stream',
    extracted_text TEXT NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The same file forwarded to several chats = ONE document, MANY sightings.
CREATE TABLE sightings (
    id          BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    sender      TEXT NOT NULL,
    chat        TEXT NOT NULL,
    sent_at     TIMESTAMPTZ NOT NULL
);
CREATE INDEX sightings_document_idx ON sightings (document_id);

CREATE TABLE chunks (
    id          BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    text        TEXT NOT NULL,
    embedding   vector(768),               -- nomic-embed-text; NULL when Ollama was down
    tsv         tsvector,
    UNIQUE (document_id, chunk_index)
);
CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv);
-- ponytail: no ANN index; exact vector scan is fine at course scale.
-- Add `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)` past ~100k chunks.

-- TODO(WS4): saved searches; newly ingested matching docs get pushed to chat_id.
CREATE TABLE standing_queries (
    id         BIGSERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    chat_id    TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- TODO(WS4): relevance feedback log ('opened', 'thumbs_up', 'thumbs_down', ...).
CREATE TABLE feedback (
    id          BIGSERIAL PRIMARY KEY,
    query_text  TEXT NOT NULL,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    action      TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
