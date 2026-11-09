# Milestone 1 — Safe extraction of ingestion and evidence logic

## Changes in this step

- Extracted `extract_chunks()` from `app.py` into `src/documind/ingestion/pdf_parser.py`.
- Extracted text matching and PDF highlighting helpers into `src/documind/evidence/highlighting.py`.
- Kept the existing Streamlit UI in `app.py`.
- Kept `render_answer_with_citations()` in `app.py` because it directly uses Streamlit widgets and session state.
- Kept retrieval, Groq generation, visual extraction, and conversation persistence unchanged.
- Added smoke tests for the extracted helper functions.

## Compatibility

`app.py` imports the extracted functions under their original names, so existing call sites remain unchanged.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Run the smoke tests with:

```bash
pytest -q
```

This is an incremental refactor, not yet the complete research application.
