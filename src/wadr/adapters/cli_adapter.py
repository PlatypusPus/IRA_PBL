"""Terminal adapter - the reference MessagingInterface implementation."""

from datetime import datetime
from pathlib import Path

from wadr.adapters.base import MessagingInterface
from wadr.models import SearchResult


class CLIAdapter(MessagingInterface):
    def ingest_folder(self, folder: Path) -> int:
        """Ingest every file under a folder (recursive). Returns files processed."""
        files = [p for p in sorted(folder.rglob("*")) if p.is_file()]
        for path in files:
            self.on_document(
                path.read_bytes(),
                path.name,
                sender="cli",
                chat="local",
                timestamp=datetime.fromtimestamp(path.stat().st_mtime),
            )
        return len(files)

    def send_results(self, chat_id: str, results: list[SearchResult]) -> None:
        if not results:
            print("No results.")
            return
        for i, r in enumerate(results, start=1):
            print(f"{i}. {r.filename}  (doc {r.document_id}, score {r.score:.4f})")
            print(f"   {r.snippet}\n")
