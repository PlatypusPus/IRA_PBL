"""wadr command-line entry point.
"""

import argparse
import logging
from pathlib import Path

from wadr.adapters.cli_adapter import CLIAdapter
from wadr.migrate import migrate
from wadr.retrieval import service

MODELS = ["hybrid", "bm25", "dense", "tfidf", "boolean"]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="wadr", description="WhatsApp Document Retrieval")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("migrate", help="apply pending schema migrations (migrations/*.sql)")

    p_ingest = sub.add_parser("ingest", help="ingest every file in a folder")
    p_ingest.add_argument("folder", type=Path)

    p_search = sub.add_parser("search", help="search ingested documents")
    p_search.add_argument("query")
    p_search.add_argument("--model", choices=MODELS, default="hybrid")
    p_search.add_argument("--top-k", type=int, default=5)

    args = parser.parse_args()
    adapter = CLIAdapter()
    if args.command == "migrate":
        applied = migrate()
        print(f"Applied: {', '.join(applied)}" if applied else "Database up to date.")
    elif args.command == "ingest":
        n = adapter.ingest_folder(args.folder)
        print(f"Processed {n} files.")
    else:
        try:
            results = service.search(args.query, model=args.model, top_k=args.top_k)
        except NotImplementedError as e:
            raise SystemExit(f"Model not implemented yet ({e}) - see TODO.md") from e
        adapter.send_results("local", results)
