"""Output CSV helpers."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_PATH = Path("output/results.csv")

OUTPUT_FIELDS = [
    "retailer_id",
    "product_id",
    "url",
    "collected_at",
    "final_price",
    "discount",
    "discount_flag",
    "unit_price_text",
    "error",
]


def ensure_output_parent(path: str | Path) -> None:
    """Ensure output directory exists."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def base_output_row(retailer_id: str | None, product_id: str | None) -> dict[str, Any]:
    """Construct default output row schema."""
    return {
        "retailer_id": retailer_id,
        "product_id": product_id,
        "url": None,
        "collected_at": None,
        "final_price": None,
        "discount": None,
        "discount_flag": False,
        "unit_price_text": None,
        "error": None,
    }


def open_output_writer(path: str | Path):
    """Return opened file handle and DictWriter with output schema header written."""
    file = Path(path).open("w", newline="", encoding="utf-8")
    writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    return file, writer
