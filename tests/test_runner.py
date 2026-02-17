from ppi.runner import NotFoundError, run_one


class FakeResponse:
    def __init__(self, status):
        self.status = status


class FakeLocator:
    def __init__(self, text=None, present=True):
        self._text = text
        self._present = present

    @property
    def first(self):
        return self

    def count(self):
        return 1 if self._present else 0

    def inner_text(self):
        return self._text


class FakePage:
    def __init__(self, status=200, locators=None):
        self._status = status
        self._locators = locators or {}

    def goto(self, url, wait_until, timeout):
        return FakeResponse(self._status)

    def wait_for_selector(self, selector, timeout, state):
        return None

    def wait_for_timeout(self, timeout_ms):
        return None

    def locator(self, selector):
        return self._locators.get(selector, FakeLocator(present=False))


BASE_CFG = {
    "base_url": "https://example.com",
    "flow": [
        {"action": "goto", "url": "{base_url}/products/{product_id}"},
        {"action": "wait_for_selector", "selector": "body", "state": "attached"},
    ],
    "pricing": {"final_price": {"selectors_priority": ["sale-price"]}},
}


def test_run_one_stores_http_status():
    page = FakePage(status=200, locators={"sale-price": FakeLocator(text="₪ 129.90")})
    out = run_one(page, BASE_CFG, {"product_id": "111"})
    assert out["http_status"] == 200
    assert out["final_price"] == "129.90"


def test_run_one_raises_on_http_404():
    page = FakePage(status=404)
    try:
        run_one(page, BASE_CFG, {"product_id": "bad"})
        assert False, "Expected NotFoundError"
    except NotFoundError as exc:
        assert str(exc) == "HTTP 404"
        assert exc.http_status == 404


def test_run_one_raises_on_soft_404_before_price_extraction():
    cfg = {
        **BASE_CFG,
        "not_found": {"any_selectors": ["text=404"]},
    }
    page = FakePage(
        status=200,
        locators={
            "text=404": FakeLocator(text="404", present=True),
            "sale-price": FakeLocator(text="₪ 59.90", present=True),
        },
    )

    try:
        run_one(page, cfg, {"product_id": "bad"})
        assert False, "Expected NotFoundError"
    except NotFoundError as exc:
        assert "Soft 404 / product not found" in str(exc)
        assert exc.http_status == 200
