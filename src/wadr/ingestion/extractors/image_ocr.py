"""OCR for images (and scanned PDF pages routed from pdf.py). TODO(WS2)."""


def extract(file_bytes: bytes) -> str:
    """OCR printed text out of an image (png/jpg).

    Intended implementation: pytesseract + Pillow (add both to pyproject).
    Requires the tesseract binary installed on the machine - document the
    install step in README when you wire this up. Return the raw recognized
    text; downstream chunking/indexing needs nothing else.
    """
    raise NotImplementedError("TODO(WS2): image OCR extractor")
