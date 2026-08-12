"""Shared value objects. Keep this import-light: engine and adapters both use it."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class SearchResult:
    chunk_id: int
    document_id: int
    filename: str
    snippet: str
    score: float
    sender: str | None = None       # who shared it (from the newest sighting)
    sent_at: datetime | None = None  # when it was last shared

    def provenance(self) -> str:
        """Human 'who + when' suffix for display; '' when unknown."""
        if not self.sender:
            return ""
        when = f", {self.sent_at:%Y-%m-%d}" if self.sent_at else ""
        # ponytail: ASCII hyphen, not em-dash - Windows consoles are cp1252 and
        # would mojibake it; renders fine in WhatsApp too.
        return f" - from {self.sender}{when}"
