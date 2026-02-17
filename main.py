from patchright.sync_api import sync_playwright

id = "7290000104683"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto(f"https://www.ybitan.co.il/search/{id}")

        # wait until product appears
        page.wait_for_selector("#product_name", timeout=30000)

        name = page.locator("#product_name").inner_text()
        print(name)

        browser.close()

main()
