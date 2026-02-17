# main.py
import os
import csv
import yaml
import re
from datetime import datetime, UTC
from patchright.sync_api import sync_playwright

CONFIG_PATH = "config/retailers/retailers.yaml"
TARGETS_PATH = "input/targets.csv"


def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_targets(path: str):
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def build_url(ret_cfg: dict, context: dict) -> str:
    for step in ret_cfg["flow"]:
        if step["action"] == "goto":
            template = step["url"]
            return template.format(base_url=ret_cfg["base_url"], **context)
    raise ValueError("No 'goto' step in flow")


def first_value(page, selectors):
    """
    Supports selector modifiers:
      - 'css' (default): returns inner_text()
      - 'css::parent_text': returns parent element inner_text()
      - 'css::attr(name)': returns get_attribute(name)
    """
    for raw in selectors:
        sel = raw.strip()
        mode = "text"
        attr = None

        if "::attr(" in sel:
            sel, rest = sel.split("::attr(", 1)
            attr = rest.rstrip(")")
            mode = "attr"
        elif sel.endswith("::parent_text"):
            sel = sel.replace("::parent_text", "")
            mode = "parent_text"

        loc = page.locator(sel).first
        if not loc.count():
            continue

        if mode == "text":
            return loc.inner_text().strip()

        if mode == "parent_text":
            return loc.locator("..").inner_text().strip()

        if mode == "attr":
            val = loc.get_attribute(attr)
            return val.strip() if val else None

        raise ValueError(f"Unsupported selector mode in: {raw}")

    return None


_num_re = re.compile(r"(\d+(?:\.\d+)?)")

def normalize_price_text(s: str | None) -> str | None:
    """
    Keep as string, but normalize common cases:
    - "₪689" -> "689"
    - "69.9" stays "69.9"
    - None stays None
    """
    if not s:
        return None
    s = s.strip()
    m = _num_re.search(s.replace(",", ""))
    return m.group(1) if m else s


def run_one(page, ret_cfg: dict, context: dict) -> dict:
    url = build_url(ret_cfg, context)
    page.goto(url, wait_until=ret_cfg.get("goto_wait_until", "domcontentloaded"))

    # Execute flow
    for step in ret_cfg["flow"]:
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

    out = {
        "url": url,
        "collected_at": datetime.now(UTC).isoformat(),
        "final_price": None,
        "discount": None,
        "discount_flag": False,
        "unit_price_text": None,
    }

    # Base final price (regular OR sale, depending on retailer's priority list)
    pricing = ret_cfg.get("pricing", {})
    fp = pricing.get("final_price", {})
    selectors_priority = fp.get("selectors_priority", [])
    if selectors_priority:
        out["final_price"] = normalize_price_text(first_value(page, selectors_priority))

    # Discount (optional)
    disc = ret_cfg.get("discount")
    if disc and disc.get("selector"):
        loc = page.locator(disc["selector"]).first
        disc_text = loc.inner_text().strip() if loc.count() else None
        out["discount"] = disc_text
        out["discount_flag"] = bool(disc_text)

        # If retailer marks discount with its own price element (e.g., KSP redPrice),
        # then discounted price should override final_price.
        if out["discount_flag"] and disc.get("discounted_price_override", False):
            out["final_price"] = normalize_price_text(disc_text)

    # Unit normalization text (NOT a discount)
    unit = ret_cfg.get("unit_price")
    if unit and unit.get("selector"):
        loc = page.locator(unit["selector"]).first
        out["unit_price_text"] = loc.inner_text().strip() if loc.count() else None

    return out


def main(headless=True):
    cfg = load_yaml(CONFIG_PATH)
    retailers = cfg.get("retailers", cfg)

    os.makedirs("output", exist_ok=True)
    output_path = "output/results.csv"

    fieldnames = [
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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()

            for row in load_targets(TARGETS_PATH):
                retailer_id = row.get("retailer_id") or row.get("retail_id") or row.get("retail")
                product_id = row.get("product_id")

                base_out = {
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

                try:
                    if not retailer_id:
                        raise ValueError("Missing retailer_id in targets.csv row")
                    if retailer_id not in retailers:
                        raise ValueError(f"Retailer '{retailer_id}' not found in config")
                    if not product_id:
                        raise ValueError("Missing product_id in targets.csv row")

                    result = run_one(page, retailers[retailer_id], row)
                    out = {**base_out, **result, "retailer_id": retailer_id, "product_id": product_id}

                except Exception as e:
                    # DEBUG dump (temporary)
                    try:
                        os.makedirs("output/debug", exist_ok=True)
                        with open("output/debug/ksp_last.html", "w", encoding="utf-8") as f:
                            f.write(page.content())
                        page.screenshot(path="output/debug/ksp_last.png", full_page=True)
                        print("Saved output/debug/ksp_last.html and ksp_last.png")
                    except Exception:
                        pass

                    out = {**base_out, "error": str(e)}


                writer.writerow(out)
                print(f"[{retailer_id}] -> {out}")

        browser.close()


if __name__ == "__main__":
    main(headless=False)
