from patchright.sync_api import sync_playwright

def test_simple():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.google.com")
        assert page.title() == "Google"
        browser.close()