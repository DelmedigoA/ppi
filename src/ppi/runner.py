"""Pipeline execution and Playwright flow runner."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from patchright.sync_api import TimeoutError as PlaywrightTimeoutError
from patchright.sync_api import sync_playwright

from .config import get_retailers, load_yaml, normalize_retailers
from .io import base_output_row, ensure_output_parent, open_output_writer
from .selectors import first_value
from .targets import load_targets

_num_re = re.compile(r"(\d+(?:\.\d+)?)")


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


def _extract_field_value(page, field_spec: dict[str, Any]) -> str | None:
    selectors = field_spec.get("selectors_priority")
    if selectors:
        return first_value(page, selectors)
    return first_value(page, [field_spec["selector"]])


def _apply_extract(page, retailer_id: str, step: dict[str, Any], out: dict[str, Any]) -> None:
    fields = step["fields"]
    for field_name, field_spec in fields.items():
        selectors = field_spec.get("selectors_priority") or [field_spec["selector"]]
        value = _extract_field_value(page, field_spec)
        optional = bool(field_spec.get("optional", False))

        if value is None:
            if optional:
                out[field_name] = None
                continue
            raise ValueError(
                f"Retailer '{retailer_id}' required field '{field_name}' could not be extracted; "
                f"tried selectors: {selectors}"
            )

        out[field_name] = value
        if field_name == "discount":
            out["discount_flag"] = True
            if field_spec.get("discounted_price_override", False):
                out["final_price"] = normalize_price_text(value)
        elif field_name == "final_price":
            out["final_price"] = normalize_price_text(value)
        elif field_name == "unit_price":
            out["unit_price_text"] = value


def execute_flow(page, retailer_id: str, ret_cfg: dict[str, Any], flow: list[dict[str, Any]], out: dict[str, Any]) -> None:
    """Run flow actions sequentially."""
    default_wait_until = ret_cfg.get("goto_wait_until", "domcontentloaded")
    goto_timeout_ms = ret_cfg.get("goto_timeout_ms", 30000)

    for step in flow:
        action = step["action"]
        if action == "goto":
            page.goto(
                step["url"].format(**out, base_url=ret_cfg["base_url"]),
                wait_until=step.get("wait_until", default_wait_until),
                timeout=step.get("timeout_ms", goto_timeout_ms),
            )
        elif action == "wait_for_selector":
            page.wait_for_selector(
                step["selector"],
                timeout=step.get("timeout_ms", 30000),
                state=step.get("state", "visible"),
            )
        elif action == "wait_for_timeout":
            page.wait_for_timeout(step.get("timeout_ms", 1000))
        elif action == "extract":
            _apply_extract(page, retailer_id, step, out)
        else:
            raise ValueError(f"Unsupported action: {action}")


def run_one(page, retailer_id: str, ret_cfg: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Scrape one target row for a retailer configuration."""
    url = build_url(ret_cfg, context)
    out: dict[str, Any] = {
        "url": url,
        "collected_at": datetime.now(UTC).isoformat(),
        "final_price": None,
        "discount": None,
        "discount_flag": False,
        "unit_price_text": None,
        **context,
    }

    try:
        execute_flow(page, retailer_id, ret_cfg, ret_cfg["flow"], out)
    except PlaywrightTimeoutError:
        if ret_cfg.get("goto_wait_until", "domcontentloaded") == "networkidle":
            page.goto(url, wait_until="domcontentloaded", timeout=ret_cfg.get("goto_timeout_ms", 30000))
            execute_flow(page, retailer_id, ret_cfg, ret_cfg["flow"][1:], out)
        else:
            raise

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
    retailers = normalize_retailers(get_retailers(cfg))

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

                    result = run_one(page, retailer_id, retailers[retailer_id], row)
                    out = {**out, **result, "retailer_id": retailer_id, "product_id": product_id}
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
