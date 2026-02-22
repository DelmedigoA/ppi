# Interactive Docs (dev tool)

Small Streamlit app that builds and serves a local, searchable codebase explainer for this repository.

## Files
- `build_index.py` — scans repo and writes `index.json`
- `app.py` — Streamlit UI
- `requirements.txt` — minimal dependencies

## Run
From repo root:

```bash
pip install -r tools/interactive_docs/requirements.txt
python tools/interactive_docs/build_index.py
streamlit run tools/interactive_docs/app.py
```

## Notes
- Works fully offline (no external APIs).
- Optional `OPENAI_API_KEY` enables a placeholder "Deep explain" action in the UI.
- Large/binary/irrelevant directories are skipped to keep indexing fast.
