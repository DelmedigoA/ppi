import os
import csv
import yaml
from datetime import datetime
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


def first_text(page, selectors):
    for sel in selectors:
        loc = page.locator(sel).first
        if loc.count():
            return loc.inner_text().strip()
    return None


def run_one(page, ret_cfg: dict, context: dict) -> dict:
    url = build_url(ret_cfg, context)
    page.goto(url, wait_until="domcontentloaded")

    # Execute flow steps
    for step in ret_cfg["flow"]:
        action = step["action"]

        if action == "goto":
            continue

        if action == "wait_for_selector":
            page.wait_for_selector(
                step["selector"],
                timeout=step.get("timeout_ms", 30000),
            )

        elif action == "wait_for_timeout":
            page.wait_for_timeout(step.get("timeout_ms", 1000))

        else:
            raise ValueError(f"Unsupported action: {action}")

    out = {
        "url": url,
        "collected_at": datetime.utcnow().isoformat(),
    }

    # Pricing logic (priority selectors)
    pricing = ret_cfg.get("pricing")
    if pricing and "final_price" in pricing:
        selectors = pricing["final_price"]["selectors_priority"]
        out["final_price"] = first_text(page, selectors)
    else:
        out["final_price"] = None

    # Discount text (optional)
    discount = ret_cfg.get("discount")
    if discount:
        sel = discount["selector"]
        loc = page.locator(sel).first
        out["discount"] = loc.inner_text().strip() if loc.count() else None
    else:
        out["discount"] = None

    return out


def main(headless=True):
    cfg = load_yaml(CONFIG_PATH)
    retailers = cfg.get("retailers", cfg)

    os.makedirs("output", exist_ok=True)
    output_path = "output/results.csv"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = None

            for row in load_targets(TARGETS_PATH):
                retail_id = (
                    row.get("retail_id")
                    or row.get("retailer_id")
                    or row.get("retail")
                )

                if not retail_id:
                    raise ValueError(
                        "targets.csv must include retail_id column"
                    )

                if retail_id not in retailers:
                    raise ValueError(f"Retailer '{retail_id}' not found in config")

                ret_cfg = retailers[retail_id]
                result = run_one(page, ret_cfg, row)

                output_row = {**row, **result}

                if writer is None:
                    writer = csv.DictWriter(
                        f, fieldnames=output_row.keys()
                    )
                    writer.writeheader()

                writer.writerow(output_row)

                print(f"[{retail_id}] -> {output_row}")

        browser.close()


if __name__ == "__main__":
    main(headless=False)
