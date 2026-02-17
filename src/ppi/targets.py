"""Target CSV loading helpers."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator


DEFAULT_TARGETS_PATH = Path("input/targets.csv")


def load_targets(path: str | Path) -> Iterator[dict[str, str]]:
    """Yield target rows from CSV."""
    with Path(path).open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            yield row
