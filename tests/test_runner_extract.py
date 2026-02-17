import pytest

from ppi.runner import run_one


class FakeLocator:
    def __init__(self, text=None, attrs=None, present=True):
        self._text = text
        self._attrs = attrs or {}
        self._present = present

    @property
    def first(self):
        return self

    def count(self):
        return 1 if self._present else 0

    def inner_text(self):
        return self._text

    def get_attribute(self, name):
        return self._attrs.get(name)

    def locator(self, selector):
        return FakeLocator(present=False)


class FakePage:
    def __init__(self, mapping):
        self.mapping = mapping

    def goto(self, *args, **kwargs):
        return None

    def wait_for_selector(self, *args, **kwargs):
        return None

    def wait_for_timeout(self, *args, **kwargs):
        return None

    def locator(self, selector):
        return self.mapping.get(selector, FakeLocator(present=False))


def test_extract_attr_priority_and_optional_fields():
    page = FakePage(
        {
            "meta[itemprop='price']": FakeLocator(attrs={"content": " 39.90\u00a0 "}),
            ".sale-price": FakeLocator(present=False),
            ".unit": FakeLocator(present=False),
        }
    )
    cfg = {
        "base_url": "https://example.com",
        "flow": [
            {"action": "goto", "url": "{base_url}/p/{product_id}"},
            {"action": "extract", "fields": {
                "final_price": {
                    "selectors_priority": ["meta[itemprop='price']::attr(content)", ".fallback"],
                },
                "discount": {
                    "selector": ".sale-price",
                    "optional": True,
                },
                "unit_price": {
                    "selector": ".unit",
                    "optional": True,
                },
            }},
        ],
    }

    out = run_one(page, "demo", cfg, {"product_id": "123"})
    assert out["final_price"] == "39.90"
    assert out["discount"] is None
    assert out["unit_price_text"] is None


def test_extract_priority_fallback():
    page = FakePage(
        {
            ".first": FakeLocator(text=""),
            ".second": FakeLocator(text=" 44.50 "),
        }
    )
    cfg = {
        "base_url": "https://example.com",
        "flow": [
            {"action": "goto", "url": "{base_url}/p/{product_id}"},
            {"action": "extract", "fields": {
                "final_price": {
                    "selectors_priority": [".missing", ".first", ".second"],
                },
            }},
        ],
    }

    out = run_one(page, "demo", cfg, {"product_id": "123"})
    assert out["final_price"] == "44.50"


def test_extract_required_field_error_message():
    page = FakePage({})
    cfg = {
        "base_url": "https://example.com",
        "flow": [
            {"action": "goto", "url": "{base_url}/p/{product_id}"},
            {"action": "extract", "fields": {"final_price": {"selectors_priority": [".a", ".b"]}}},
        ],
    }

    with pytest.raises(ValueError, match="Retailer 'demo' required field 'final_price'.*\\['.a', '.b'\\]"):
        run_one(page, "demo", cfg, {"product_id": "123"})
