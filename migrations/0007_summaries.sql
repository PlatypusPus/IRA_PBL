-- 0007: a one-line summary per document, so a digest can say what
-- "wa-1788370118.jpeg" actually is.
--
-- On the document, not the sighting: it describes the bytes, and identical
-- bytes are one document here regardless of who received them. Empty means
-- "not summarised yet" - they are filled in lazily, never during ingest.
ALTER TABLE documents ADD COLUMN summary TEXT NOT NULL DEFAULT '';
