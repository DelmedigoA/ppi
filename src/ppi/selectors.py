"""Selector parsing and extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal


SelectorMode = Literal["text", "parent_text", "attr"]


@dataclass(frozen=True)
class SelectorSpec:
    selector: str
    mode: SelectorMode
    attr: str | None = None


def parse_selector(raw: str) -> SelectorSpec:
    """Parse selector modifiers like ::attr(name) and ::parent_text."""
    sel = raw.strip()
    if "::attr(" in sel:
        selector, rest = sel.split("::attr(", 1)
        return SelectorSpec(selector=selector, mode="attr", attr=rest.rstrip(")"))
    if sel.endswith("::parent_text"):
        return SelectorSpec(selector=sel.replace("::parent_text", ""), mode="parent_text")
    return SelectorSpec(selector=sel, mode="text")


def normalize_extracted_text(value: str | None) -> str | None:
    """Trim extracted text and normalize NBSP characters."""
    if value is None:
        return None
    return value.replace("\u00a0", " ").strip()


def first_value(page, selectors: Iterable[str]) -> str | None:
    """Return the first available value for a selector priority list."""
    for raw in selectors:
        spec = parse_selector(raw)
        loc = page.locator(spec.selector).first
        if not loc.count():
            continue

        if spec.mode == "text":
            value = normalize_extracted_text(loc.inner_text())
        elif spec.mode == "parent_text":
            value = normalize_extracted_text(loc.locator("..").inner_text())
        else:
            val = loc.get_attribute(spec.attr)
            value = normalize_extracted_text(val)

        if value:
            return value

    return None
