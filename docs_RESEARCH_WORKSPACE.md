# DocuMind Research workspace

The new Streamlit page is `pages/1_Research_Workspace.py`.

Core modules:
- `src/documind/research_library.py`: SQLite schema, paper import, metadata, collections, analysis cache.
- `src/documind/research_analysis.py`: nine structured analysis modes, including the eight planned research tools plus paper summary.

The original `app.py`, RAG modules, conversation storage and evidence-highlighting
modules are retained. The new page uses the same `documind.db` database file but
creates separate `research_*` tables.

Run `streamlit run app.py` and select **Research Workspace** from Streamlit's
left navigation.
