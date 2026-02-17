"""Pipeline execution and Playwright flow runner."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from patchright.sync_api import TimeoutError as PlaywrightTimeoutError
from patchright.sync_api import sync_playwright

from .config import get_retailers, load_yaml
from .io import base_output_row, ensure_output_parent, open_output_writer
from .selectors import first_value
from .targets import load_targets

_num_re = re.compile(r"(\d+(?:\.\d+)?)")


class NotFoundError(ValueError):
    """Raised when a page resolves to a hard/soft not-found state."""

    def __init__(self, message: str, *, http_status: int | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status


def normalize_price_text(value: str | None) -> str | None:
    """Keep price as a string while extracting the first numeric token when present."""
    if not value:
        return None
    stripped = value.strip()
    match = _num_re.search(stripped.replace(",", ""))
    return match.group(1) if match else stripped


def build_url(ret_cfg: dict[str, Any], context: dict[str, Any]) -> str:
    """Build product URL from retailer flow goto template."""
    for step in ret_cfg["flow"]:
        if step["action"] == "goto":
            template = step["url"]
            return template.format(base_url=ret_cfg["base_url"], **context)
    raise ValueError("No 'goto' step in flow")


def execute_flow(page, flow: list[dict[str, Any]]) -> None:
    """Run flow actions after initial page goto."""
    for step in flow:
        action = step["action"]
        if action == "goto":
            continue
        if action == "wait_for_selector":
            page.wait_for_selector(
                step["selector"],
                timeout=step.get("timeout_ms", 30000),
                state=step.get("state", "visible"),
            )
        elif action == "wait_for_timeout":
            page.wait_for_timeout(step.get("timeout_ms", 1000))
        else:
            raise ValueError(f"Unsupported action: {action}")


def detect_not_found_selector(page, ret_cfg: dict[str, Any]) -> str | None:
    """Return the first matched not_found selector for soft-404 detection."""
    not_found_cfg = ret_cfg.get("not_found", {})
    selectors = not_found_cfg.get("any_selectors", [])
    for sel in selectors:
        if page.locator(sel).count() > 0:
            return sel
    return None


def run_one(page, ret_cfg: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Scrape one target row for a retailer configuration."""
    url = build_url(ret_cfg, context)
    goto_wait_until = ret_cfg.get("goto_wait_until", "domcontentloaded")
    goto_timeout_ms = ret_cfg.get("goto_timeout_ms", 30000)

    try:
        response = page.goto(url, wait_until=goto_wait_until, timeout=goto_timeout_ms)
    except PlaywrightTimeoutError:
        if goto_wait_until == "networkidle":
            # Some retailer pages keep background connections alive and never
            # become "networkidle" even when all product data is already visible.
            # Fall back to DOM readiness to avoid hanging on valid pages.
            response = page.goto(url, wait_until="domcontentloaded", timeout=goto_timeout_ms)
        else:
            raise

    http_status = response.status if response else None
    if http_status == 404:
        raise NotFoundError("HTTP 404", http_status=http_status)

    execute_flow(page, ret_cfg["flow"])

    not_found_selector = detect_not_found_selector(page, ret_cfg)
    if not_found_selector:
        raise NotFoundError(
            f"Soft 404 / product not found (matched: {not_found_selector})",
            http_status=http_status,
        )

    out: dict[str, Any] = {
        "url": url,
        "collected_at": datetime.now(UTC).isoformat(),
        "http_status": http_status,
        "final_price": None,
        "discount": None,
        "discount_flag": False,
        "unit_price_text": None,
    }

    pricing = ret_cfg.get("pricing", {})
    selectors_priority = pricing.get("final_price", {}).get("selectors_priority", [])
    if selectors_priority:
        out["final_price"] = normalize_price_text(first_value(page, selectors_priority))

    disc = ret_cfg.get("discount")
    if disc and disc.get("selector"):
        loc = page.locator(disc["selector"]).first
        disc_text = loc.inner_text().strip() if loc.count() else None
        out["discount"] = disc_text
        out["discount_flag"] = bool(disc_text)
        if out["discount_flag"] and disc.get("discounted_price_override", False):
            out["final_price"] = normalize_price_text(disc_text)

    unit = ret_cfg.get("unit_price")
    if unit and unit.get("selector"):
        loc = page.locator(unit["selector"]).first
        out["unit_price_text"] = loc.inner_text().strip() if loc.count() else None

    return out


def run_pipeline(
    config_path: str,
    targets_path: str,
    output_path: str,
    *,
    headless: bool,
) -> None:
    """Run the full scrape pipeline and write output CSV."""
    cfg = load_yaml(config_path)
    retailers = get_retailers(cfg)

    ensure_output_parent(output_path)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        output_file, writer = open_output_writer(output_path)
        with output_file:
            for row in load_targets(targets_path):
                retailer_id = row.get("retailer_id") or row.get("retail_id") or row.get("retail")
                product_id = row.get("product_id")
                out = base_output_row(retailer_id, product_id)

                try:
                    if not retailer_id:
                        raise ValueError("Missing retailer_id in targets.csv row")
                    if retailer_id not in retailers:
                        raise ValueError(f"Retailer '{retailer_id}' not found in config")
                    if not product_id:
                        raise ValueError("Missing product_id in targets.csv row")

                    result = run_one(page, retailers[retailer_id], row)
                    out = {**out, **result, "retailer_id": retailer_id, "product_id": product_id}
                except NotFoundError as exc:
                    out = {
                        **out,
                        "http_status": exc.http_status,
                        "error": "NOT_FOUND",
                    }
                except Exception as exc:
                    try:
                        debug_dir = Path("output/debug")
                        debug_dir.mkdir(parents=True, exist_ok=True)
                        (debug_dir / "ksp_last.html").write_text(page.content(), encoding="utf-8")
                        page.screenshot(path=str(debug_dir / "ksp_last.png"), full_page=True)
                        print("Saved output/debug/ksp_last.html and ksp_last.png")
                    except Exception:
                        pass
                    out = {**out, "error": str(exc)}

                writer.writerow(out)
                print(f"[{retailer_id}] -> {out}")

        browser.close()
