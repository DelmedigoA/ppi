"""Streamlit app for interactive local repo docs."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

try:
    import streamlit as st
except ModuleNotFoundError:  # pragma: no cover
    class _StreamlitStub:
        def cache_data(self, **_kwargs):
            def decorator(func):
                return func

            return decorator

        def __getattr__(self, _name):
            def _noop(*_args, **_kwargs):
                return None

            return _noop

    st = _StreamlitStub()

TOOL_DIR = Path(__file__).resolve().parent
INDEX_PATH = TOOL_DIR / "index.json"


@st.cache_data(show_spinner=False)
def load_index() -> dict:
    if not INDEX_PATH.exists():
        return {}
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {max-width: 1200px; padding-top: 1.5rem;}
        .card {border: 1px solid #e5e7eb; border-radius: 8px; padding: 1rem; background: #fff; margin-bottom: 1rem;}
        .muted {color: #6b7280; font-size: 0.9rem;}
        h1,h2,h3 {letter-spacing: -0.01em;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def where_used(repo_root: str, symbol: str) -> list[str]:
    if not symbol:
        return []
    try:
        out = subprocess.check_output(
            ["rg", "-n", f"\\b{symbol}\\b", "--glob", "*.py", repo_root],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out.strip().splitlines()[:30]
    except Exception:
        return []


def maybe_deep_explain(file_path: str, content: str) -> None:
    if not os.getenv("OPENAI_API_KEY"):
        return
    with st.expander("Optional: Deep explain (requires OPENAI_API_KEY)"):
        st.caption("Deep explain integration can be wired to your preferred OpenAI client.")
        if st.button("Deep explain", key=f"deep-{file_path}"):
            st.info("OPENAI_API_KEY detected, but no external API call is made in MVP mode.")


def render_overview(data: dict) -> None:
    overview = data.get("overview", {})
    st.subheader("Project overview")
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("### Architecture")
        st.json(overview.get("folders", {}))
    with col2:
        st.markdown("### Entrypoints")
        for ep in overview.get("entrypoints", []):
            st.code(ep)
        st.markdown("### How to run")
        for cmd in overview.get("how_to_run", []):
            st.code(cmd)

    st.markdown("### Top 5 important modules")
    for item in overview.get("top_modules", []):
        st.markdown(f"- **{item['path']}** — {item['reason']}")


def render_file(data: dict, selected_file: str) -> None:
    entry = data["files"][selected_file]
    repo_root = data["overview"]["root"]
    full_path = Path(repo_root) / selected_file

    st.subheader(selected_file)
    st.markdown(f"<div class='card'><div class='muted'>{entry['summary']}</div></div>", unsafe_allow_html=True)

    with st.expander("Key dependencies/imports", expanded=True):
        st.write(entry.get("imports", []) or ["None detected"])

    with st.spinner("Loading source..."):
        content = full_path.read_text(encoding="utf-8", errors="ignore")

    st.code(content, language="python" if selected_file.endswith(".py") else None)

    st.markdown("### Explain symbol")
    symbols = entry.get("symbols", [])
    options = [s["name"] for s in symbols]
    selected_symbol = st.selectbox("Choose function/class", [""] + options)
    if selected_symbol:
        symbol = next(s for s in symbols if s["name"] == selected_symbol)
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.write(f"**Type:** {symbol['kind']}")
        st.write(f"**Line:** {symbol['line']}")
        if symbol.get("signature"):
            st.code(symbol["signature"])
            if st.button("Copy signature", key=f"copy-{selected_file}-{selected_symbol}"):
                st.toast("Signature copied", icon="✅")
        st.write(f"**Docstring:** {symbol.get('docstring') or 'No docstring'}")
        refs = where_used(repo_root, selected_symbol)
        with st.expander("Where used", expanded=True):
            st.code("\n".join(refs) if refs else "No references found")
        st.write(
            f"Plain-English: `{selected_symbol}` is a {symbol['kind']} in `{selected_file}` that helps implement this module's behavior."
        )
        st.markdown("</div>", unsafe_allow_html=True)

    maybe_deep_explain(selected_file, content)


def main() -> None:
    st.set_page_config(page_title="Interactive Docs", layout="wide")
    _inject_css()
    data = load_index()

    st.title("Interactive Docs")
    if not data:
        st.warning("No index found. Run: python tools/interactive_docs/build_index.py")
        return

    st.caption(f"Repo: {data.get('repo')} • Last index build: {data.get('built_at')}")

    file_paths = list(data["files"].keys())
    query = st.sidebar.text_input("Search files or symbols")
    st.sidebar.markdown("---")

    filtered = []
    for path in file_paths:
        entry = data["files"][path]
        symbol_names = " ".join(s["name"] for s in entry.get("symbols", []))
        haystack = f"{path} {symbol_names}".lower()
        if not query or query.lower() in haystack:
            filtered.append(path)

    page = st.sidebar.radio("Page", ["Project overview", "File browser"])

    if page == "Project overview":
        render_overview(data)
        return

    selected_file = st.sidebar.selectbox("File", filtered if filtered else ["No results"])
    if selected_file == "No results":
        st.info("No files match the current search.")
        return
    render_file(data, selected_file)


if __name__ == "__main__":
    main()
