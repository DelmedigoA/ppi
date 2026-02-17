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


def first_value(page, selectors: Iterable[str]) -> str | None:
    """Return the first available value for a selector priority list."""
    for raw in selectors:
        spec = parse_selector(raw)
        loc = page.locator(spec.selector).first
        if not loc.count():
            continue

        if spec.mode == "text":
            return loc.inner_text().strip()
        if spec.mode == "parent_text":
            return loc.locator("..").inner_text().strip()
        if spec.mode == "attr":
            val = loc.get_attribute(spec.attr)
            return val.strip() if val else None

    return None
