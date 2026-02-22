from pathlib import Path

import pytest

import ppi.runner as runner


class RecordingPage:
    def __init__(self):
        self.calls = []

    def goto(self, *args, **kwargs):
        self.calls.append(("goto", args, kwargs))

    def wait_for_selector(self, *args, **kwargs):
        self.calls.append(("wait_for_selector", args, kwargs))

    def wait_for_timeout(self, *args, **kwargs):
        self.calls.append(("wait_for_timeout", args, kwargs))

    def content(self):
        return "<html>debug</html>"

    def screenshot(self, *args, **kwargs):
        self.calls.append(("screenshot", args, kwargs))


class DummyWriter:
    def __init__(self):
        self.rows = []

    def writerow(self, row):
        self.rows.append(row)


class DummyBrowser:
    def __init__(self, page):
        self.page = page

    def new_page(self):
        return self.page

    def close(self):
        return None


class DummySyncPlaywright:
    def __init__(self, page):
        self.chromium = self
        self._page = page

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def launch(self, headless):
        return DummyBrowser(self._page)


def test_normalize_price_text_and_build_url_errors():
    assert runner.normalize_price_text(None) is None
    assert runner.normalize_price_text("  only text  ") == "only text"
    assert runner.normalize_price_text("$ 1,234.56") == "1234.56"

    with pytest.raises(ValueError, match="No 'goto' step"):
        runner.build_url({"flow": [{"action": "extract"}], "base_url": "https://x"}, {})


def test_execute_flow_unsupported_action_raises():
    page = RecordingPage()
    with pytest.raises(ValueError, match="Unsupported action"):
        runner.execute_flow(page, "ret", {"base_url": "https://x"}, [{"action": "unknown"}], {})


def test_run_one_networkidle_timeout_fallback(monkeypatch):
    page = RecordingPage()
    calls = {"n": 0}

    def fake_execute_flow(_page, _retailer_id, _ret_cfg, flow, _out):
        calls["n"] += 1
        if calls["n"] == 1:
            raise runner.PlaywrightTimeoutError("timed out")
        # second call should skip goto
        assert flow[0]["action"] == "extract"

    monkeypatch.setattr(runner, "execute_flow", fake_execute_flow)

    cfg = {
        "base_url": "https://example.com",
        "goto_wait_until": "networkidle",
        "goto_timeout_ms": 1234,
        "flow": [
            {"action": "goto", "url": "{base_url}/p/{product_id}"},
            {"action": "extract", "fields": {"final_price": {"selector": ".price", "optional": True}}},
        ],
    }

    out = runner.run_one(page, "demo", cfg, {"product_id": "1"})
    assert out["url"].endswith("/p/1")
    assert any(c[0] == "goto" for c in page.calls)



def test_run_one_retries_until_success(monkeypatch):
    page = RecordingPage()
    calls = {"n": 0}

    def flaky_execute_flow(_page, _retailer_id, _ret_cfg, _flow, out):
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("transient")
        out["final_price"] = "19.90"

    monkeypatch.setattr(runner, "execute_flow", flaky_execute_flow)

    cfg = {
        "base_url": "https://example.com",
        "flow": [
            {"action": "goto", "url": "{base_url}/p/{product_id}"},
            {"action": "retry", "limit": 3},
            {"action": "extract", "fields": {"final_price": {"selector": ".price", "optional": True}}},
        ],
    }

    out = runner.run_one(page, "demo", cfg, {"product_id": "1"})
    assert out["tries"] == 3
    assert out["final_price"] == "19.90"


def test_run_one_retries_respects_limit(monkeypatch):
    page = RecordingPage()

    def always_fail(*_args, **_kwargs):
        raise ValueError("still failing")

    monkeypatch.setattr(runner, "execute_flow", always_fail)

    cfg = {
        "base_url": "https://example.com",
        "flow": [
            {"action": "goto", "url": "{base_url}/p/{product_id}"},
            {"action": "retry", "limit": 2},
            {"action": "extract", "fields": {"final_price": {"selector": ".price", "optional": True}}},
        ],
    }

    with pytest.raises(ValueError, match="still failing"):
        runner.run_one(page, "demo", cfg, {"product_id": "1"})


def test_run_pipeline_captures_row_errors_and_writes_output(monkeypatch, tmp_path: Path):
    page = RecordingPage()
    writer = DummyWriter()

    monkeypatch.setattr(runner, "load_yaml", lambda _: {"retailers": {"ok": {"base_url": "https://e", "flow": []}}})
    monkeypatch.setattr(runner, "get_retailers", lambda cfg: cfg["retailers"])
    monkeypatch.setattr(runner, "normalize_retailers", lambda r: r)
    monkeypatch.setattr(runner, "load_targets", lambda _: [{"retailer_id": "missing", "product_id": "p1"}])
    monkeypatch.setattr(runner, "sync_playwright", lambda: DummySyncPlaywright(page))
    monkeypatch.setattr(runner, "open_output_writer", lambda _: (open(tmp_path / "out.csv", "w", encoding="utf-8"), writer))

    out_dir = tmp_path / "results" / "results.csv"
    runner.run_pipeline("cfg.yaml", "targets.csv", str(out_dir), headless=True)

    assert writer.rows and "error" in writer.rows[0]
    assert "not found in config" in writer.rows[0]["error"]
    assert (Path("output/debug") / "ksp_last.html").exists()
