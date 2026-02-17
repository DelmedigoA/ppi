import pytest

from ppi.config import normalize_retailers


def test_normalize_adds_legacy_extract_when_missing():
    retailers = {
        "legacy": {
            "base_url": "https://example.com",
            "flow": [{"action": "goto", "url": "{base_url}/p/{product_id}"}],
            "pricing": {"final_price": {"selectors_priority": [".price"]}},
            "discount": {"selector": ".sale", "optional": True},
            "unit_price": {"selector": ".unit", "optional": True},
        }
    }

    normalized = normalize_retailers(retailers)
    extract = normalized["legacy"]["flow"][-1]
    assert extract["action"] == "extract"
    assert set(extract["fields"].keys()) == {"final_price", "discount", "unit_price"}


def test_normalize_keeps_explicit_extract_precedence():
    retailers = {
        "modern": {
            "base_url": "https://example.com",
            "flow": [
                {"action": "goto", "url": "{base_url}/p/{product_id}"},
                {"action": "extract", "fields": {"final_price": {"selector": ".price"}}},
            ],
            "pricing": {"final_price": {"selectors_priority": [".legacy"]}},
        }
    }

    normalized = normalize_retailers(retailers)
    extract_steps = [s for s in normalized["modern"]["flow"] if s["action"] == "extract"]
    assert len(extract_steps) == 1
    assert extract_steps[0]["fields"]["final_price"]["selector"] == ".price"


def test_normalize_rejects_invalid_extract_spec():
    retailers = {
        "broken": {
            "base_url": "https://example.com",
            "flow": [
                {"action": "goto", "url": "{base_url}/p/{product_id}"},
                {
                    "action": "extract",
                    "fields": {
                        "final_price": {
                            "selector": ".price",
                            "selectors_priority": [".a", ".b"],
                        }
                    },
                },
            ],
        }
    }

    with pytest.raises(ValueError, match="exactly one of selector or selectors_priority"):
        normalize_retailers(retailers)
