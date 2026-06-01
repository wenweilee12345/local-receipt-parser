"""Export a parsed Receipt to CSV (and a tidy items DataFrame)."""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .parser import Receipt


def receipt_to_csv(receipt: "Receipt") -> str:
    """Render a Receipt as CSV text.

    Layout: one row per line item, then a blank line, then summary rows.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)

    writer.writerow(["merchant", receipt.merchant])
    writer.writerow(["date", receipt.date])
    writer.writerow(["currency", receipt.currency])
    writer.writerow([])

    writer.writerow(["description", "quantity", "price"])
    for item in receipt.items:
        writer.writerow([item.description, _num(item.quantity), _num(item.price)])

    writer.writerow([])
    if receipt.subtotal is not None:
        writer.writerow(["subtotal", "", _num(receipt.subtotal)])
    if receipt.tax is not None:
        writer.writerow(["tax", "", _num(receipt.tax)])
    if receipt.total is not None:
        writer.writerow(["total", "", _num(receipt.total)])

    return buf.getvalue()


def receipt_to_rows(receipt: "Receipt") -> list[dict]:
    """Items as a list of dicts (handy for a pandas DataFrame in the UI)."""
    return [
        {
            "description": i.description,
            "quantity": i.quantity,
            "price": i.price,
        }
        for i in receipt.items
    ]


def _num(value: float) -> str:
    """Format numbers without trailing ``.0`` noise for whole quantities."""
    if value == int(value):
        return str(int(value))
    return f"{value:.2f}"
