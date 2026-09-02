"""PDF text extraction via PyMuPDF, with OCR fallback for scanned pages."""

import logging

import fitz  # PyMuPDF

log = logging.getLogger(__name__)

# Render scanned pages at ~144 dpi - enough for tesseract, cheap enough for a
# phone photo. PyMuPDF's default is 72 dpi, which mangles small print.
RENDER_ZOOM = 2.0


def extract(file_bytes: bytes) -> str:
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        pages = []
        for page in doc:
            text = page.get_text().strip()
            if text:
                pages.append(text)
                continue
            # empty text layer -> it's a scan: render and OCR. Lazy import so a
            # missing tesseract/pillow never breaks text-only PDFs.
            from wadr.ingestion.extractors import image_ocr

            try:
                pix = page.get_pixmap(matrix=fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM))
                pages.append(image_ocr.extract(pix.tobytes("png")))
            except Exception as e:  # noqa: BLE001 - a bad page must not kill the whole PDF
                log.warning("page %d OCR failed: %s - kept empty", page.number + 1, e)
                pages.append("")
        return "\n".join(pages)
