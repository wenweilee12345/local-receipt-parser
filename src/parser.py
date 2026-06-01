"""Parse raw OCR text from a receipt into a structured Receipt.

The parser is deliberately OCR-agnostic: it operates on plain text, so it can
be unit-tested without Tesseract or any image at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import List, Optional

# A money amount like 12.34 or 1,234.56 (optionally prefixed by a currency sign).
_MONEY = r"[$€£]?\s*-?\d{1,3}(?:,\d{3})*\.\d{2}"
_MONEY_RE = re.compile(_MONEY)

# Trailing price at the end of a line, e.g. "Milk 2L            3.99"
_LINE_ITEM_RE = re.compile(
    r"^(?P<desc>.+?)\s+(?P<price>" + _MONEY + r")\s*$"
)

# Optional quantity prefix, e.g. "2 x Coffee" or "3  Bagel"
_QTY_RE = re.compile(r"^(?P<qty>\d{1,3})\s*(?:x|@)?\s+(?P<rest>.+)$", re.IGNORECASE)

_DATE_RE = re.compile(
    r"\b("
    r"\d{4}[-/]\d{1,2}[-/]\d{1,2}"          # 2026-06-01
    r"|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}"        # 06/01/2026
    r"|[A-Z][a-z]{2,8}\s+\d{1,2},?\s+\d{4}"  # June 1, 2026
    r")\b"
)

# Keywords that mark summary lines rather than purchasable items.
_SUBTOTAL_KEYS = ("subtotal", "sub total", "sub-total")
_TAX_KEYS = ("tax", "vat", "gst", "hst", "sales tax")
_TOTAL_KEYS = ("total", "amount due", "balance due", "grand total")
_SKIP_KEYS = (
    "change", "cash", "card", "visa", "mastercard", "debit", "credit",
    "tendered", "approval", "auth", "ref", "tel", "phone", "thank",
    "cashier", "register", "store #", "qty", "item", "description",
)


@dataclass
class LineItem:
    description: str
    quantity: float
    price: float  # line total for this item


@dataclass
class Receipt:
    merchant: str = ""
    date: str = ""
    currency: str = "$"
    items: List[LineItem] = field(default_factory=list)
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None

    @property
    def items_total(self) -> float:
        return round(sum(i.price for i in self.items), 2)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["items_total"] = self.items_total
        return d


def _to_float(money: str) -> float:
    return float(re.sub(r"[^\d.\-]", "", money))


def _detect_currency(text: str) -> str:
    for sign in ("$", "€", "£"):
        if sign in text:
            return sign
    return "$"


def _lowered(line: str) -> str:
    return line.strip().lower()


def _contains_key(line: str, keys) -> bool:
    low = _lowered(line)
    return any(k in low for k in keys)


def _last_amount(line: str) -> Optional[float]:
    matches = _MONEY_RE.findall(line)
    return _to_float(matches[-1]) if matches else None


def parse_receipt(text: str) -> Receipt:
    """Parse OCR text into a :class:`Receipt`."""
    raw_lines = [ln.rstrip() for ln in text.splitlines()]
    lines = [ln for ln in raw_lines if ln.strip()]

    receipt = Receipt(currency=_detect_currency(text))

    # Merchant: first line that is mostly letters (skip numeric/address noise).
    for ln in lines[:4]:
        letters = sum(c.isalpha() for c in ln)
        if letters >= 3 and letters >= len(ln) * 0.4:
            receipt.merchant = ln.strip()
            break

    # Date: first matching pattern anywhere.
    m = _DATE_RE.search(text)
    if m:
        receipt.date = m.group(1)

    for ln in lines:
        low = _lowered(ln)

        # Summary lines first — they take precedence over item matching.
        if _contains_key(ln, _TOTAL_KEYS) and not _contains_key(ln, _SUBTOTAL_KEYS):
            amt = _last_amount(ln)
            if amt is not None:
                receipt.total = amt
            continue
        if _contains_key(ln, _SUBTOTAL_KEYS):
            amt = _last_amount(ln)
            if amt is not None:
                receipt.subtotal = amt
            continue
        if _contains_key(ln, _TAX_KEYS):
            amt = _last_amount(ln)
            if amt is not None:
                receipt.tax = amt
            continue
        if _contains_key(ln, _SKIP_KEYS):
            continue

        # Otherwise, try to read it as "<description> ... <price>".
        item_match = _LINE_ITEM_RE.match(ln)
        if not item_match:
            continue
        desc = item_match.group("desc").strip(" .-")
        price = _to_float(item_match.group("price"))

        qty = 1.0
        qty_match = _QTY_RE.match(desc)
        if qty_match:
            qty = float(qty_match.group("qty"))
            desc = qty_match.group("rest").strip()

        # Guard against picking up stray numbers with no real description.
        if len(re.sub(r"[^A-Za-z]", "", desc)) < 2:
            continue

        receipt.items.append(LineItem(description=desc, quantity=qty, price=price))

    # If total is missing but we have subtotal+tax, infer it.
    if receipt.total is None and receipt.subtotal is not None:
        tax = receipt.tax or 0.0
        receipt.total = round(receipt.subtotal + tax, 2)

    return receipt
