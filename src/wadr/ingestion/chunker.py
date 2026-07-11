"""Split extracted text into overlapping chunks for embedding + lexical indexing."""

CHUNK_SIZE = 1000  # characters
OVERLAP = 200


def chunk(text: str, size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> list[str]:
    """Sliding character window; each cut snaps back to the last space so words
    stay whole, and consecutive chunks share ~`overlap` characters of context.

    Whitespace (incl. newlines) is collapsed to single spaces first.
    ponytail: char-based, not token-based; revisit only if embedding quality demands it.
    """
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("need size > 0 and 0 <= overlap < size")
    text = " ".join(text.split())
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while True:
        end = start + size
        if end >= len(text):
            chunks.append(text[start:].strip())
            break
        cut = text.rfind(" ", start, end)
        if cut <= start:  # one unbroken token longer than `size`: hard cut
            cut = end
        chunks.append(text[start:cut].strip())
        start = max(cut - overlap, start + 1)
    return [c for c in chunks if c]
