"""DOCX text extraction. TODO(WS2)."""


def extract(file_bytes: bytes) -> str:
    """Extract plain text from a .docx file.

    Intended implementation: python-docx (add it to pyproject when you start);
    join paragraph texts with newlines and include table cell text. A .docx is
    just a zip - stdlib zipfile + parsing word/document.xml is an acceptable
    dependency-free alternative.
    """
    raise NotImplementedError("TODO(WS2): docx extractor")
