"""Shared value objects. Keep this import-light: engine and adapters both use it."""

from dataclasses import dataclass


@dataclass
class SearchResult:
    chunk_id: int
    document_id: int
    filename: str
    snippet: str
    score: float
