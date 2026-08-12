-- 0002: store the original file bytes so "/get <n>" can send documents back.
-- Rows ingested before this migration have content = NULL (re-share to populate).
ALTER TABLE documents ADD COLUMN content BYTEA;
