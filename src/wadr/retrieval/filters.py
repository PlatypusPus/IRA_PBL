"""Query-token filters: from:/in:/before:/after:/type:. TODO(WS4).

Example:
    parse("invoice from:dad in:family before:2026-01-01 type:pdf")
    -> ("invoice", Filters(sender="dad", chat="family",
                           before=date(2026, 1, 1), doc_type="pdf"))

parse() strips the tokens; the remaining text goes to the ranking models, and
the Filters constrain SQL (sightings.sender / sightings.chat /
sightings.sent_at, documents.mime_type).
"""

from dataclasses import dataclass
from datetime import date


@dataclass
class Filters:
    sender: str | None = None
    chat: str | None = None
    before: date | None = None
    after: date | None = None
    doc_type: str | None = None


def parse(query: str) -> tuple[str, Filters]:
    """Split filter tokens out of a raw query; unknown tokens stay in the text.

    Dates are ISO (YYYY-MM-DD); type: matches a mime_type suffix ("pdf",
    "docx", "png", ...). Raise ValueError on malformed dates.
    """
    raise NotImplementedError("TODO(WS4): filter parsing")
