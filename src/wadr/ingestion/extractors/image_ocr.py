"""OCR for images (and scanned PDF pages routed from pdf.py).

Needs the tesseract binary on the system - pytesseract is just a wrapper,
so `pip install pytesseract` alone is not enough. See the README for the
system install step.
"""

import io

import pytesseract
from PIL import Image


def extract(file_bytes: bytes) -> str:
    """OCR printed text out of an image (png/jpg) via pytesseract + Pillow."""
    return pytesseract.image_to_string(Image.open(io.BytesIO(file_bytes)))
