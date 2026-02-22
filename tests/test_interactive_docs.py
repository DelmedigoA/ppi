from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parents[1] / "tools" / "interactive_docs"
sys.path.insert(0, str(TOOL_DIR))

import build_index  # noqa: E402


def _load_app_module():
    spec = importlib.util.spec_from_file_location("interactive_docs_app", TOOL_DIR / "app.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_index_builds_for_repo(tmp_path: Path) -> None:
    output = tmp_path / "index.json"
    payload = build_index.build_index(Path.cwd(), output)
    assert output.exists()
    assert payload["files"]
    parsed = json.loads(output.read_text(encoding="utf-8"))
    assert "overview" in parsed


def test_ignore_rules_work(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    (root / "src").mkdir(parents=True)
    (root / ".git" / "hidden.py").write_text("print('x')", encoding="utf-8")
    (root / "src" / "visible.py").write_text("def ok():\n    return 1\n", encoding="utf-8")

    payload = build_index.build_index(root, tmp_path / "out.json")
    assert "src/visible.py" in payload["files"]
    assert ".git/hidden.py" not in payload["files"]


def test_ast_extracts_functions_and_classes() -> None:
    source = """
class Alpha:
    \"\"\"alpha doc\"\"\"
    pass

def beta(x, y=1):
    \"\"\"beta doc\"\"\"
    return x + y
"""
    symbols, imports = build_index.parse_python_symbols(source)
    names = [s.name for s in symbols]
    assert "Alpha" in names
    assert "beta" in names
    beta = next(s for s in symbols if s.name == "beta")
    assert beta.signature == "beta(x, y)"
    assert imports == []


def test_streamlit_app_imports_cleanly() -> None:
    module = _load_app_module()
    assert hasattr(module, "main")
