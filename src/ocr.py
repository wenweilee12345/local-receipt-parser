"""OCR layer: turn an uploaded image or PDF into plain text.

Multiple backends are supported and chosen at call time:

* ``tesseract`` - local, offline, default (via ``pytesseract``).
* ``openai``    - OpenAI vision models (needs ``OPENAI_API_KEY``).
* ``google``    - Google Cloud Vision (needs Google credentials).

Everything degrades gracefully so the app can show a helpful message instead of
crashing when a binary, library, or API key is missing.
"""

from __future__ import annotations

import base64
import io
import os
import shutil

BACKENDS = ("tesseract", "openai", "google")
DEFAULT_BACKEND = "tesseract"

# Prompt used by LLM-vision backends to behave like an OCR engine.
_OCR_PROMPT = (
    "Transcribe ALL text from this receipt exactly as it appears. Preserve line "
    "breaks, the order of lines, item names, quantities, and prices. Do not add, "
    "summarize, reformat, or explain anything. Output only the raw text."
)


class OCRUnavailable(RuntimeError):
    """Raised when the requested OCR backend is not usable."""


# --- Backend availability ---------------------------------------------------

def tesseract_available() -> bool:
    """True if the Tesseract binary is importable and on PATH."""
    try:
        import pytesseract
    except ImportError:
        return False
    if shutil.which("tesseract") is not None:
        return True
    try:
        cmd = pytesseract.pytesseract.tesseract_cmd
        return bool(cmd) and shutil.which(cmd) is not None
    except Exception:
        return False


def openai_available() -> bool:
    """True if the OpenAI SDK is installed and an API key is configured."""
    try:
        import openai  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("OPENAI_API_KEY"))


def google_available() -> bool:
    """True if google-cloud-vision is installed and credentials are present."""
    try:
        from google.cloud import vision  # noqa: F401
    except ImportError:
        return False
    return bool(
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or os.environ.get("GOOGLE_API_KEY")
    )


def backend_status() -> dict[str, tuple[bool, str]]:
    """Map each backend to (available, human-readable hint)."""
    return {
        "tesseract": (
            tesseract_available(),
            "Local OCR via Tesseract." if tesseract_available()
            else "Install Tesseract and `pip install pytesseract`.",
        ),
        "openai": (
            openai_available(),
            "OpenAI vision ready." if openai_available()
            else "Set OPENAI_API_KEY and `pip install openai`.",
        ),
        "google": (
            google_available(),
            "Google Cloud Vision ready." if google_available()
            else "Set Google credentials and `pip install google-cloud-vision`.",
        ),
    }


def available_backends() -> list[str]:
    """Backends that are usable right now, in preference order."""
    status = backend_status()
    return [name for name in BACKENDS if status[name][0]]


# --- Per-backend image OCR --------------------------------------------------

def _tesseract_image(data: bytes, lang: str = "eng") -> str:
    if not tesseract_available():
        raise OCRUnavailable(
            "Tesseract OCR is not installed. See the README for install steps."
        )
    from PIL import Image, ImageOps
    import pytesseract

    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    img = ImageOps.grayscale(img)
    img = ImageOps.autocontrast(img)
    return pytesseract.image_to_string(img, lang=lang)


def _openai_image(data: bytes, model: str | None = None) -> str:
    if not openai_available():
        raise OCRUnavailable(
            "OpenAI backend unavailable. Install `openai` and set OPENAI_API_KEY."
        )
    from openai import OpenAI

    model = model or os.environ.get("OPENAI_OCR_MODEL", "gpt-4o-mini")
    b64 = base64.b64encode(data).decode("ascii")
    data_url = f"data:image/png;base64,{b64}"

    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _OCR_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def _google_image(data: bytes) -> str:
    if not google_available():
        raise OCRUnavailable(
            "Google backend unavailable. Install `google-cloud-vision` and set "
            "GOOGLE_APPLICATION_CREDENTIALS."
        )
    from google.cloud import vision

    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=data)
    resp = client.document_text_detection(image=image)
    if resp.error.message:
        raise OCRUnavailable(f"Google Vision error: {resp.error.message}")
    return resp.full_text_annotation.text


def image_bytes_to_text(
    data: bytes, backend: str = DEFAULT_BACKEND, lang: str = "eng"
) -> str:
    """OCR a single image (PNG/JPG/...) with the chosen backend."""
    if backend not in BACKENDS:
        raise ValueError(
            f"Unknown OCR backend {backend!r}. Choose from {', '.join(BACKENDS)}."
        )
    if backend == "tesseract":
        return _tesseract_image(data, lang=lang)
    if backend == "openai":
        return _openai_image(data)
    return _google_image(data)


# --- PDF handling -----------------------------------------------------------

def pdf_bytes_to_text(
    data: bytes, backend: str = DEFAULT_BACKEND, lang: str = "eng"
) -> str:
    """Extract text from a PDF.

    Uses the embedded text layer when present (free and exact); otherwise
    renders each page to an image and runs the chosen OCR backend.
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
            pix = page.get_pixmap(dpi=200)
            out.append(image_bytes_to_text(pix.tobytes("png"), backend, lang))
    return "\n".join(out)


def extract_text(
    filename: str, data: bytes, backend: str = DEFAULT_BACKEND, lang: str = "eng"
) -> str:
    """Dispatch to the right pipeline based on file extension."""
    if backend not in BACKENDS:
        raise ValueError(
            f"Unknown OCR backend {backend!r}. Choose from {', '.join(BACKENDS)}."
        )
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return pdf_bytes_to_text(data, backend=backend, lang=lang)
    return image_bytes_to_text(data, backend=backend, lang=lang)
