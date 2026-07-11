"""Plain text / markdown passthrough."""


def extract(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="replace")
