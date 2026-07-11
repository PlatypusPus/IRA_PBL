"""Relevance judgments loader. TODO(WS3).

File format - evaluation/queries.jsonl, one JSON object per line:

    {"qid": "q01",
     "query": "tf-idf lecture notes",
     "relevant": {"<file_hash>": 3, "<other_file_hash>": 1}}

- qid: stable id q01..q40 (~40 queries; cover every extractor type, phrase
  queries, and filter-style queries).
- relevant: documents.file_hash -> graded relevance 0-3 (omit grade-0 docs).
  Keyed by file_hash rather than row id so judgments survive a DB wipe and
  re-ingest.
"""

from pathlib import Path


def load(path: Path) -> list[dict]:
    """Parse queries.jsonl into [{"qid", "query", "relevant"}, ...].

    Validate: unique qids, non-empty query, grades are ints in 1..3.
    Raise ValueError with the offending line number on bad input.
    """
    raise NotImplementedError("TODO(WS3): judgments loader")
