import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from src.parser import parse_receipt  # noqa: E402
from src.export import receipt_to_csv  # noqa: E402
from src import ocr  # noqa: E402

GROCERY = """FRESHMART GROCERS
123 Imaginary Ave, Nowhere City
Tel: 555-0100
Date: 2026-06-01

Bananas 1kg            1.29
2 x Almond Milk        7.98
Sourdough Loaf         4.50
Cheddar Cheese         6.25
Free Range Eggs        3.99
Olive Oil 500ml        8.75

Subtotal              32.76
Sales Tax              2.62
Total                 35.38

VISA ************1234
Thank you for shopping!
"""


def test_merchant_and_date():
    r = parse_receipt(GROCERY)
    assert r.merchant == "FRESHMART GROCERS"
    assert r.date == "2026-06-01"


def test_line_items_extracted():
    r = parse_receipt(GROCERY)
    descs = [i.description for i in r.items]
    assert "Bananas 1kg" in descs
    assert "Olive Oil 500ml" in descs
    # 6 purchasable lines; summary + card lines must be excluded.
    assert len(r.items) == 6


def test_quantity_prefix_parsed():
    r = parse_receipt(GROCERY)
    milk = next(i for i in r.items if "Almond Milk" in i.description)
    assert milk.quantity == 2
    assert milk.price == 7.98


def test_summary_amounts():
    r = parse_receipt(GROCERY)
    assert r.subtotal == 32.76
    assert r.tax == 2.62
    assert r.total == 35.38


def test_card_and_total_not_treated_as_items():
    r = parse_receipt(GROCERY)
    descs = " ".join(i.description for i in r.items).lower()
    assert "visa" not in descs
    assert "total" not in descs


def test_total_inferred_when_missing():
    text = "SHOP\nWidget   10.00\nSubtotal   10.00\nTax   1.00\n"
    r = parse_receipt(text)
    assert r.total == 11.00


def test_currency_detection():
    assert parse_receipt("Cafe\nTea  £2.50\nTotal  £2.50").currency == "£"
    assert parse_receipt("Cafe\nTea  3.00\nTotal  3.00").currency == "$"


def test_csv_export_roundtrip():
    r = parse_receipt(GROCERY)
    csv_text = receipt_to_csv(r)
    assert "merchant,FRESHMART GROCERS" in csv_text
    assert "Bananas 1kg" in csv_text
    assert "total,,35.38" in csv_text
    # Header row present.
    assert "description,quantity,price" in csv_text


def test_empty_input_is_safe():
    r = parse_receipt("")
    assert r.items == []
    assert r.total is None


# --- OCR backend abstraction (no API keys / Tesseract required) -------------

def test_backend_registry_has_three_engines():
    assert ocr.BACKENDS == ("tesseract", "openai", "google")
    status = ocr.backend_status()
    assert set(status) == set(ocr.BACKENDS)
    for available, hint in status.values():
        assert isinstance(available, bool)
        assert isinstance(hint, str) and hint


def test_unknown_backend_raises_clear_error():
    with pytest.raises(ValueError, match="Unknown OCR backend"):
        ocr.image_bytes_to_text(b"x", backend="not-a-backend")
    with pytest.raises(ValueError, match="Unknown OCR backend"):
        ocr.extract_text("a.png", b"x", backend="nope")


def test_backend_dispatch_routes_to_selected_engine(monkeypatch):
    calls = {}

    def fake_image(data, backend="tesseract", lang="eng"):
        calls["backend"] = backend
        return "MOCKED"

    monkeypatch.setattr(ocr, "image_bytes_to_text", fake_image)
    assert ocr.extract_text("receipt.png", b"x", backend="openai") == "MOCKED"
    assert calls["backend"] == "openai"


def test_available_backends_subset_of_all():
    avail = ocr.available_backends()
    assert all(b in ocr.BACKENDS for b in avail)
