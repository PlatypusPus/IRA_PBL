"""wadr command-line entry point - operator tasks only.

The product surface is the web app and WhatsApp itself; this exists to set up
a database and, when needed, create the first account.
"""

import argparse
import getpass
import logging
import sys

from wadr import accounts
from wadr.migrate import migrate


def main() -> None:
    # Windows consoles default to cp1252 and we print arbitrary text; one odd
    # glyph is otherwise enough to kill a command with UnicodeEncodeError.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="wadr", description="WhatsApp Document Retrieval")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("migrate", help="apply pending schema migrations (migrations/*.sql)")

    p_user = sub.add_parser("adduser", help="create an account from the terminal")
    p_user.add_argument("email")

    p_key = sub.add_parser("apikey", help="mint an API key for an agent (MCP)")
    p_key.add_argument("email")
    p_key.add_argument("--label", default="Agent key")

    sub.add_parser("mcp", help="run the MCP server over stdio (needs WADR_API_KEY)")

    p_digest = sub.add_parser("digest", help="push each user a summary of what arrived")
    p_digest.add_argument("--days", type=int, default=7, help="window for a user's first digest")
    p_digest.add_argument("--dry-run", action="store_true", help="print it, send nothing")

    args = parser.parse_args()

    if args.command == "digest":
        from wadr.digest import send_all

        sent = send_all(args.days, args.dry_run)
        for user_id, text in sent.items():
            print(f"--- user {user_id} ---\n{text}\n")
        print(f"{len(sent)} digest(s) {'built' if args.dry_run else 'sent'}.")
        return

    if args.command == "mcp":
        from wadr.mcp_server import main as mcp_main

        mcp_main()
        return

    if args.command == "apikey":
        from wadr.db import get_conn

        with get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE email = %s", (args.email.strip().lower(),)
            ).fetchone()
        if row is None:
            raise SystemExit(f"no account for {args.email}")
        print(accounts.create_api_key(row[0], args.label))
        print("Shown once - store it now.", file=sys.stderr)
        return

    if args.command == "migrate":
        applied = migrate()
        print(f"Applied: {', '.join(applied)}" if applied else "Database up to date.")
        return

    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Repeat: "):
        raise SystemExit("passwords do not match")
    try:
        user_id = accounts.sign_up(args.email, password)
    except accounts.AuthError as e:
        raise SystemExit(str(e)) from e
    print(f"Created user {user_id} ({args.email}). Sign in on the web app to link a number.")
