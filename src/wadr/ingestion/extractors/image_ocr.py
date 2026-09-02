"""OCR for images (and scanned PDF pages routed from pdf.py).

Needs the tesseract binary on the system - pytesseract is just a wrapper,
so `pip install pytesseract` alone is not enough. See the README for the
system install step.
"""

import io

import pytesseract
from PIL import Image, ImageOps


def extract(file_bytes: bytes) -> str:
    """OCR printed text out of an image (png/jpg) via pytesseract + Pillow."""
    with Image.open(io.BytesIO(file_bytes)) as img:
        # Phone cameras store the sensor's raw orientation and record the real
        # one in an EXIF tag, so a photo that looks upright is often sideways in
        # the pixels - and tesseract reads sideways text as garbage. Straighten
        # it first; a no-op for images without the tag.
        return pytesseract.image_to_string(ImageOps.exif_transpose(img))
