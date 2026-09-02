"""WADR - WhatsApp Document Retrieval. See README.md and TODO.md."""

import os
from pathlib import Path

# Load the repo's .env before anything reads os.environ, so `uv run ...` works
# without the caller having exported WADR_BRIDGE_TOKEN first. Real environment
# variables win - this only fills in what is missing.
#
# ponytail: hand-rolled KEY=value instead of python-dotenv; the file has one
# line in it. Add the dependency if quoting or interpolation ever matters.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
if _ENV_FILE.exists():
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        key = key.strip()
        if key and not key.startswith("#"):
            os.environ.setdefault(key, value.strip().strip("'\""))
