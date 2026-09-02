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

    args = parser.parse_args()

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
