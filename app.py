"""Local Receipt Parser - Streamlit UI.

Upload a receipt image or PDF (or pick a bundled fake sample), extract items,
totals and taxes, review them, and download a clean CSV.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from src.ocr import extract_text, tesseract_available, OCRUnavailable
from src.parser import parse_receipt
from src.export import receipt_to_csv

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "samples")

st.set_page_config(page_title="Local Receipt Parser", page_icon="🧾", layout="centered")

st.title("🧾 Local Receipt Parser")
st.caption(
    "Upload a receipt image or PDF, extract items, totals and taxes, and export CSV. "
    "Runs locally with Tesseract OCR - nothing leaves your machine."
)


def list_samples() -> dict[str, str]:
    """Map a friendly label to each bundled sample PNG."""
    if not os.path.isdir(SAMPLES_DIR):
        return {}
    out = {}
    for fn in sorted(os.listdir(SAMPLES_DIR)):
        if fn.endswith(".png"):
            label = fn.replace("_", " ").replace(".png", "").title()
            out[label] = os.path.join(SAMPLES_DIR, fn)
    return out


def sample_groundtruth(png_path: str) -> str | None:
    """Return the bundled OCR text for a sample, if present."""
    txt = png_path[:-4] + ".txt"
    return open(txt, encoding="utf-8").read() if os.path.exists(txt) else None


# --- Sidebar: status + options ---------------------------------------------

with st.sidebar:
    st.header("Status")
    if tesseract_available():
        st.success("Tesseract OCR detected.")
    else:
        st.warning(
            "Tesseract not found. You can still try the bundled samples "
            "(they ship with text), but uploads won't OCR until you "
            "[install Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html)."
        )
    st.divider()
    st.markdown(
        "**Privacy:** images are processed in memory and never uploaded "
        "anywhere. Sample receipts are entirely fictional."
    )


# --- Input: sample or upload -----------------------------------------------

tab_sample, tab_upload = st.tabs(["Try a sample", "Upload your own"])

text: str | None = None
source_label = ""
preview_path: str | None = None

with tab_sample:
    samples = list_samples()
    if not samples:
        st.info("No bundled samples found. Run `samples/generate_samples.py`.")
    else:
        choice = st.selectbox("Pick a fake receipt", list(samples.keys()))
        preview_path = samples[choice]
        source_label = choice
        if st.button("Parse sample", type="primary"):
            if tesseract_available():
                with open(preview_path, "rb") as fh:
                    try:
                        text = extract_text(os.path.basename(preview_path), fh.read())
                    except OCRUnavailable:
                        text = sample_groundtruth(preview_path)
            else:
                # Demo-safe fallback: use the shipped ground-truth text.
                text = sample_groundtruth(preview_path)

with tab_upload:
    up = st.file_uploader(
        "Receipt image or PDF", type=["png", "jpg", "jpeg", "pdf", "bmp", "tiff"]
    )
    if up is not None:
        preview_path = None
        source_label = up.name
        if st.button("Parse upload", type="primary"):
            try:
                text = extract_text(up.name, up.getvalue())
            except OCRUnavailable as exc:
                st.error(str(exc))


# --- Preview the chosen image ----------------------------------------------

if preview_path and os.path.exists(preview_path):
    st.image(preview_path, caption=source_label, width=320)


# --- Results ----------------------------------------------------------------

if text:
    receipt = parse_receipt(text)

    st.subheader("Extracted receipt")
    c1, c2, c3 = st.columns(3)
    c1.metric("Merchant", receipt.merchant or "-")
    c2.metric("Date", receipt.date or "-")
    c3.metric("Items", len(receipt.items))

    if receipt.items:
        df = pd.DataFrame(
            [
                {
                    "Description": i.description,
                    "Qty": i.quantity,
                    "Price": i.price,
                }
                for i in receipt.items
            ]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No line items detected. The OCR text may be too noisy.")

    s1, s2, s3 = st.columns(3)
    s1.metric("Subtotal", f"{receipt.currency}{receipt.subtotal:.2f}" if receipt.subtotal is not None else "-")
    s2.metric("Tax", f"{receipt.currency}{receipt.tax:.2f}" if receipt.tax is not None else "-")
    s3.metric("Total", f"{receipt.currency}{receipt.total:.2f}" if receipt.total is not None else "-")

    # Sanity check: do the items roughly add up to the subtotal?
    if receipt.subtotal is not None and receipt.items:
        diff = abs(receipt.items_total - receipt.subtotal)
        if diff > 0.02:
            st.warning(
                f"Items sum to {receipt.currency}{receipt.items_total:.2f}, "
                f"but subtotal reads {receipt.currency}{receipt.subtotal:.2f}. "
                "Review the OCR text below."
            )

    csv_text = receipt_to_csv(receipt)
    safe_name = (source_label or "receipt").rsplit(".", 1)[0].replace(" ", "_")
    st.download_button(
        "⬇️ Download CSV",
        data=csv_text,
        file_name=f"{safe_name}.csv",
        mime="text/csv",
        type="primary",
    )

    with st.expander("Raw OCR text"):
        st.code(text)
