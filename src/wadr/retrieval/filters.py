"""Query-token filters: from:/in:/before:/after:/type:.

Example:
    parse("invoice from:dad in:family before:2026-01-01 type:pdf")
    -> ("invoice", Filters(sender="dad", chat="family",
                           before=date(2026, 1, 1), doc_type="pdf"))

parse() strips the tokens; the remaining text goes to the ranking models, and
the Filters constrain SQL (sightings.sender / sightings.chat /
sightings.sent_at, documents.mime_type).
"""

import re
from dataclasses import dataclass
from datetime import date


@dataclass
class Filters:
    sender: str | None = None
    chat: str | None = None
    before: date | None = None
    after: date | None = None
    doc_type: str | None = None

    def __bool__(self) -> bool:
        """True when anything is actually constrained - lets callers skip the SQL."""
        return any(vars(self).values())


# \b keeps "berlin:x" from matching "in:"; unknown prefixes fall through as text.
_TOKEN = re.compile(r"\b(from|in|before|after|type):(\S+)")
_FIELD = {"from": "sender", "in": "chat", "before": "before", "after": "after", "type": "doc_type"}


def parse(query: str) -> tuple[str, Filters]:
    """Split filter tokens out of a raw query; unknown tokens stay in the text.

    Dates are ISO (YYYY-MM-DD); type: matches a mime_type suffix ("pdf",
    "docx", "png", ...). Raise ValueError on malformed dates.
    """
    found: dict = {}

    def take(m: re.Match) -> str:
        key, value = m.group(1), m.group(2)
        if key in ("before", "after"):
            try:
                found[_FIELD[key]] = date.fromisoformat(value)
            except ValueError as e:
                raise ValueError(f"{key}: needs an ISO date (YYYY-MM-DD), got {value!r}") from e
        else:
            found[_FIELD[key]] = value.lower()
        return ""

    clean = _TOKEN.sub(take, query)
    return " ".join(clean.split()), Filters(**found)


def where(f: Filters | None) -> tuple[str, list]:
    """SQL predicate + params for a query with `documents d` in scope.

    Returns ("", []) when nothing is filtered, else (" AND ...", params) ready
    to append to an existing WHERE-less or WHERE-ful query via the caller.
    """
    if not f:
        return "", []
    clauses: list[str] = []
    params: list = []
    if f.doc_type:
        # mime suffix OR filename extension: "pdf" -> application/pdf, but
        # "docx" only ever shows up in the filename (its mime ends in "document").
        clauses.append("(d.mime_type LIKE %s OR d.filename ILIKE %s)")
        params += [f"%{f.doc_type}", f"%.{f.doc_type}"]
    for column, value in (("sender", f.sender), ("chat", f.chat)):
        if value:
            clauses.append(
                f"EXISTS (SELECT 1 FROM sightings s WHERE s.document_id = d.id"
                f" AND s.{column} ILIKE %s)"  # column is a literal above, not user input
            )
            params.append(f"%{value}%")
    # One sighting has to satisfy both ends of the range, so they share an EXISTS.
    date_clauses, date_params = [], []
    if f.before:
        date_clauses.append("s.sent_at < %s")
        date_params.append(f.before)
    if f.after:
        date_clauses.append("s.sent_at >= %s")
        date_params.append(f.after)
    if date_clauses:
        clauses.append(
            "EXISTS (SELECT 1 FROM sightings s WHERE s.document_id = d.id"
            f" AND {' AND '.join(date_clauses)})"
        )
        params += date_params
    return "".join(f" AND {c}" for c in clauses), params
