"""OCR layer: turn an uploaded image or PDF into plain text.

Tesseract (via ``pytesseract``) is the default engine. Everything here degrades
gracefully so the rest of the app can give a useful message instead of crashing
when the Tesseract binary or optional libraries are missing.
"""

from __future__ import annotations

import io
import shutil
from typing import Union


class OCRUnavailable(RuntimeError):
    """Raised when no OCR backend is usable."""


def tesseract_available() -> bool:
    """True if the Tesseract binary is importable and on PATH."""
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    return shutil.which("tesseract") is not None or _pytesseract_cmd_exists()


def _pytesseract_cmd_exists() -> bool:
    try:
        import pytesseract

        cmd = pytesseract.pytesseract.tesseract_cmd
        return bool(cmd) and shutil.which(cmd) is not None
    except Exception:
        return False


def image_bytes_to_text(data: bytes, lang: str = "eng") -> str:
    """OCR a single image (PNG/JPG/...) given as raw bytes."""
    if not tesseract_available():
        raise OCRUnavailable(
            "Tesseract OCR is not installed. See the README for install steps."
        )
    from PIL import Image, ImageOps
    import pytesseract

    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    # Grayscale + autocontrast generally improves OCR on photos of receipts.
    img = ImageOps.grayscale(img)
    img = ImageOps.autocontrast(img)
    return pytesseract.image_to_string(img, lang=lang)


def pdf_bytes_to_text(data: bytes, lang: str = "eng") -> str:
    """Extract text from a PDF.

    First tries the embedded text layer (fast, exact). If a page has little or
    no text, it is rendered to an image and OCR'd as a fallback.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover
        raise OCRUnavailable(
            "PDF support needs PyMuPDF. Install with `pip install pymupdf`."
        ) from exc

    out = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            text = page.get_text().strip()
            if len(text) >= 20:
                out.append(text)
                continue
            # Scanned/image PDF page -> render and OCR.
            pix = page.get_pixmap(dpi=200)
            out.append(image_bytes_to_text(pix.tobytes("png"), lang=lang))
    return "\n".join(out)


def extract_text(filename: str, data: bytes, lang: str = "eng") -> str:
    """Dispatch to the right backend based on file extension."""
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return pdf_bytes_to_text(data, lang=lang)
    return image_bytes_to_text(data, lang=lang)
