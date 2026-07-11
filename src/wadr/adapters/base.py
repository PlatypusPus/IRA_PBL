"""Adapter contract.

HARD RULE: dependency points inward only - the engine (ingestion / indexing /
retrieval / evaluation) never imports wadr.adapters. Adapters call the engine.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from wadr.ingestion import router
from wadr.models import SearchResult


class MessagingInterface(ABC):
    """A messaging channel that hands documents in and carries results out."""

    def on_document(
        self, file_bytes: bytes, filename: str, sender: str, chat: str, timestamp: datetime
    ) -> int | None:
        """Inbound document -> ingestion pipeline. Returns document id, or None if skipped."""
        return router.ingest(file_bytes, filename, sender, chat, timestamp)

    @abstractmethod
    def send_results(self, chat_id: str, results: list[SearchResult]) -> None:
        """Deliver search results back over this channel."""
