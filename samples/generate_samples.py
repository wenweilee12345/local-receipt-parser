"""Generate fake receipt images for demos and tests.

Every merchant, address, and card number here is fictional. Run this to
(re)build the PNGs and matching ground-truth .txt files:

    uv run --with pillow python samples/generate_samples.py
"""

from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))

# --- Fictional receipt data (safe for public demos) -------------------------

RECEIPTS = {
    "grocery_receipt": [
        "FRESHMART GROCERS",
        "123 Imaginary Ave, Nowhere City",
        "Tel: 555-0100",
        "Date: 2026-06-01",
        "",
        "Bananas 1kg            1.29",
        "2 x Almond Milk        7.98",
        "Sourdough Loaf         4.50",
        "Cheddar Cheese         6.25",
        "Free Range Eggs        3.99",
        "Olive Oil 500ml        8.75",
        "",
        "Subtotal              32.76",
        "Sales Tax              2.62",
        "Total                 35.38",
        "",
        "VISA ************1234",
        "Thank you for shopping!",
    ],
    "cafe_receipt": [
        "THE BUSY BEAN CAFE",
        "42 Pretend Street",
        "Date: 05/28/2026",
        "",
        "Cappuccino             4.25",
        "Avocado Toast          9.50",
        "2 x Croissant          6.00",
        "Orange Juice           3.75",
        "",
        "Subtotal              23.50",
        "Tax                    1.88",
        "Total                 25.38",
        "",
        "Card ************9999",
        "Have a lovely day!",
    ],
    "hardware_receipt": [
        "FIXIT HARDWARE SUPPLY",
        "9 Fictional Road, Testville",
        "June 1, 2026",
        "",
        "Hammer 16oz            12.99",
        "Wood Screws Box        5.49",
        "3 x Paint Brush        14.97",
        "Sandpaper Pack         4.25",
        "Wall Anchors           3.50",
        "Measuring Tape         8.99",
        "",
        "Subtotal              50.19",
        "GST                    2.51",
        "Total                 52.70",
        "",
        "DEBIT ************4242",
        "Returns within 30 days",
    ],
}


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Find a monospace TrueType font, falling back to PIL's default."""
    candidates = [
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/cour.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/Library/Fonts/Courier New.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def render(name: str, lines: list[str]) -> None:
    font = _load_font(22)
    pad, line_h, width = 30, 30, 460
    height = pad * 2 + line_h * len(lines)

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((pad, pad + i * line_h), line, fill="black", font=font)

    png_path = os.path.join(HERE, f"{name}.png")
    txt_path = os.path.join(HERE, f"{name}.txt")
    img.save(png_path)
    with open(txt_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"wrote {png_path} and {txt_path}")


def main() -> None:
    for name, lines in RECEIPTS.items():
        render(name, lines)


if __name__ == "__main__":
    main()
