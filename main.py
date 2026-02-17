import csv
import yaml
from patchright.sync_api import sync_playwright
import os

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


def run_one(page, ret_cfg: dict, context: dict) -> dict:
    url = build_url(ret_cfg, context)
    page.goto(url, wait_until="domcontentloaded")

    # Execute flow
    for step in ret_cfg["flow"]:
        action = step["action"]
        if action == "goto":
            continue
        if action == "wait_for_selector":
            page.wait_for_selector(step["selector"], timeout=step.get("timeout_ms", 30000))
        elif action == "wait_for_timeout":
            page.wait_for_timeout(step.get("timeout_ms", 1000))
        else:
            raise ValueError(f"Unsupported action: {action}")

    # Extract
    out = {"url": url}
    for field, spec in ret_cfg.get("extract", {}).items():
        if isinstance(spec, str):
            loc = page.locator(spec).first
            out[field] = loc.inner_text().strip() if loc.count() else None
        else:
            selector = spec["selector"]
            take = spec.get("take", "text")

            loc = page.locator(selector).first
            if not loc.count():
                out[field] = None
                continue

            if take == "text":
                out[field] = loc.inner_text().strip()
            elif take == "parent_text":
                out[field] = loc.locator("..").inner_text().strip()
            else:
                raise ValueError(f"Unsupported extract.take: {take}")

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
            writer = None  # initialize later after first result

            for row in load_targets(TARGETS_PATH):
                retail_id = row.get("retail_id") or row.get("retailer_id") or row.get("retail")
                if not retail_id:
                    raise ValueError("targets.csv must include retail_id column")

                ret_cfg = retailers[retail_id]
                result = run_one(page, ret_cfg, row)

                # merge input + result
                output_row = {**row, **result}

                # initialize CSV header dynamically
                if writer is None:
                    writer = csv.DictWriter(f, fieldnames=output_row.keys())
                    writer.writeheader()

                writer.writerow(output_row)

                print(f"[{retail_id}] {output_row}")

        browser.close()


if __name__ == "__main__":
    main(headless=False)
