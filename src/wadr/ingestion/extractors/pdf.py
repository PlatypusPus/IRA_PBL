"""PDF text extraction via PyMuPDF."""

import fitz  # PyMuPDF


def extract(file_bytes: bytes) -> str:
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        # TODO(WS2): pages whose text layer is empty are scans - render the
        # page to an image and route it through image_ocr.extract() instead.
        return "\n".join(page.get_text() for page in doc)
