from patchright.sync_api import sync_playwright


def test_lvl1():
    """
    Open a simple html website and get the title.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.google.com", wait_until="domcontentloaded")
        assert "Google" in page.title()
        browser.close()

def test_lvl2():
    """
    Open Ybitan search page and wait for JS rendering.
    Verify product name for known barcode.
    """
    id = "7290000104683"
    expected = "שעועית ירוקה שלמה"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"https://www.ybitan.co.il/search/{id}", wait_until="domcontentloaded")
        page.wait_for_selector("#product_name", timeout=30_000)
        name = page.locator("#product_name").first.inner_text().strip()
        assert expected in name
        browser.close()
