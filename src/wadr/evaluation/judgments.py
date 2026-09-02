"""Relevance judgments loader.

File format - evaluation/queries.jsonl, one JSON object per line:

    {"qid": "q01",
     "query": "tf-idf lecture notes",
     "relevant": {"<file_hash>": 3, "<other_file_hash>": 1}}

- qid: stable id q01..q40 (~40 queries; cover every extractor type, phrase
  queries, and filter-style queries).
- relevant: documents.file_hash -> graded relevance 0-3 (omit grade-0 docs).
  Keyed by file_hash rather than row id so judgments survive a DB wipe and
  re-ingest.

The validation below is deliberately strict and reports the offending LINE
NUMBER: these files are hand-written by several people over several sittings,
and a silently-dropped judgment quietly corrupts every number in the report.
"""

import json
from pathlib import Path


def load(path: Path) -> list[dict]:
    """Parse queries.jsonl into [{"qid", "query", "relevant"}, ...].

    Validate: unique qids, non-empty query, grades are ints in 1..3.
    Raise ValueError with the offending line number on bad input.
    """
    rows: list[dict] = []
    seen_qids: dict[str, int] = {}

    for line_number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue  # blank lines and comments are convenient while grading

        def bad(message: str, line_number: int = line_number) -> ValueError:
            # line_number bound as a default: without it this closes over the
            # loop variable and every error would report the LAST line's number
            return ValueError(f"{path}:{line_number}: {message}")

        try:
            row = json.loads(line)
        except json.JSONDecodeError as e:
            raise bad(f"not valid JSON ({e.msg})") from e
        if not isinstance(row, dict):
            raise bad(f"expected a JSON object, got {type(row).__name__}")

        missing = {"qid", "query", "relevant"} - set(row)
        if missing:
            raise bad(f"missing key(s): {', '.join(sorted(missing))}")

        qid = row["qid"]
        if not isinstance(qid, str) or not qid.strip():
            raise bad(f"qid must be a non-empty string, got {qid!r}")
        if qid in seen_qids:
            raise bad(f"duplicate qid {qid!r} (first seen on line {seen_qids[qid]})")
        seen_qids[qid] = line_number

        if not isinstance(row["query"], str) or not row["query"].strip():
            raise bad(f"query must be a non-empty string, got {row['query']!r}")

        relevant = row["relevant"]
        if not isinstance(relevant, dict):
            raise bad(f"relevant must be an object, got {type(relevant).__name__}")
        for file_hash, grade in relevant.items():
            # bool first: in Python True is an int, and a stray `true` grade
            # would otherwise sail through as 1
            if isinstance(grade, bool) or not isinstance(grade, int):
                raise bad(f"grade for {file_hash!r} must be an int, got {grade!r}")
            if not 1 <= grade <= 3:
                raise bad(f"grade for {file_hash!r} must be 1..3, got {grade} "
                          "(omit the document entirely instead of grading it 0)")

        rows.append({"qid": qid, "query": row["query"], "relevant": relevant})

    if not rows:
        raise ValueError(f"{path}: no judgments found")
    return rows
