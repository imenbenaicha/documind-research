# DocuMind Research

**Understand. Compare. Validate. Discover.**

DocuMind Research is a Streamlit application for discussing PDF papers and organizing research analysis in one workspace. It combines document-grounded chat with a shared paper library and LLM-assisted research workflows.

> **Project status:** Active prototype / MVP. Metadata extraction and AI-generated analyses are best-effort and must be checked against the original paper. The current importer requires selectable PDF text; OCR for scanned-only papers is not included in the Research Library importer.

## What it currently includes

### Papers Discussions

- Upload PDF documents and ask questions about their contents.
- Multi-document conversation workflow and saved conversation history.
- Text extraction and overlapping chunking with page/document metadata.
- Hybrid retrieval combining Sentence Transformers semantic similarity and BM25 keyword retrieval using Reciprocal Rank Fusion (RRF).
- Groq-powered answer generation and visual-content analysis for PDF content.
- Supporting document/page references and a PDF viewer with evidence-highlighting support.

### Research Workspace

- A shared research paper library: PDFs uploaded through Papers Discussions are registered in the workspace.
- SHA-256-based duplicate detection for paper imports.
- Editable paper metadata: title, authors, year, venue, DOI, abstract, keywords and notes.
- Research collections and cached analysis results.
- Nine LLM-assisted analysis modes:
  1. Research Paper Brief
  2. Methodology extraction
  3. Reproducibility analysis
  4. Benchmark comparison
  5. Agreement, differences and contradiction analysis
  6. Paper-to-code analysis
  7. Citation-context analysis
  8. Research knowledge graph extraction
  9. Mathematical and algorithm analysis

Analysis output is generated from extracted PDF text. It is not independently verified against external sources, and it should not be treated as proof that an experiment is reproducible or that two results are comparable.

## Architecture

```text
                         Streamlit application
                    ┌──────────────┴──────────────┐
                    │                             │
             Papers Discussions             Research Workspace
                    │                             │
          PDF text / visual extraction       Shared paper library
                    │                             │
             Chunking + metadata       Metadata / collections / notes
                    │                             │
       Semantic retrieval + BM25          Research analysis prompts
                    │                             │
               RRF retrieval                 Groq LLM analysis
                    │                             │
            Groq answer generation        Structured results + evidence
                    │                             │
          Citations / PDF viewer             Overview / technical / evidence
                    └──────────────┬──────────────┘
                                   │
                           Local SQLite database
```

## Technology stack

- Python and Streamlit
- Groq API for language and vision model calls
- Sentence Transformers (`all-MiniLM-L6-v2`) for semantic embeddings
- BM25 (`rank-bm25`) and Reciprocal Rank Fusion for hybrid retrieval
- PyMuPDF and pypdf for PDF rendering and text extraction
- Pillow for image processing
- scikit-learn for cosine similarity
- SQLite for local conversation and research-library persistence

## Project layout

```text
.
├── Papers_Discussions.py          # Main Streamlit entry point
├── app.py                         # Retained compatibility entry point
├── pages/
│   └── 1_Research_Workspace.py    # Research Workspace page
├── src/documind/
│   ├── conversation_store.py
│   ├── generation.py
│   ├── metadata_extraction.py
│   ├── research_analysis.py
│   ├── research_library.py
│   ├── semantic_search.py
│   ├── vision.py
│   ├── ingestion/pdf_parser.py
│   └── evidence/highlighting.py
├── evaluation/                    # Retrieval evaluation scripts and fixtures
├── tests/                         # Focused module tests
├── config.py
└── requirements.txt
```

Papers_Discussions.py is the recommended application entry point. app.py is retained as a compatibility entry point.

## Getting started

### Requirements

- Python 3.11 is the recommended starting point for this pinned dependency set.
- A Groq API key.

### 1. Clone the repository

```bash
git clone https://github.com/imenbenaicha/documind-ai.git
cd documind-ai
```

The repository name may remain `documind-ai` on GitHub while the application is presented as **DocuMind Research**.

### 2. Create a virtual environment

**macOS / Linux**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

**Windows PowerShell**

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure the API key

Copy `.env.example` to `.env` and add your own Groq API key:

```env
GROQ_API_KEY=your_groq_api_key_here
DOCUMIND_RESEARCH_MODEL=openai/gpt-oss-20b
```

Keep `.env` private. Never commit API keys, credentials or private PDFs.

### 5. Run the application

```bash
streamlit run Papers_Discussions.py
```

Open the local URL printed by Streamlit in your browser.

## Run tests

Install pytest if it is not already available:

```bash
python -m pip install pytest
pytest -q
```

The included tests cover selected metadata-extraction, PDF-ingestion and evidence-helper behaviors. They are not a full end-to-end test of the Streamlit application or Groq API integration.

## Evaluation utilities

The `evaluation/` directory contains retrieval evaluation and top-k optimization scripts, test cases and recorded evaluation outputs. Inspect the scripts and their expected input paths before running them against your own documents.

## Current limitations

- Metadata extraction is heuristic. Author names, publication venues, abstracts and DOI fields can be missed or misidentified depending on PDF layout.
- The Research Library importer extracts selectable text. Scanned-only PDFs need OCR before they can be imported there.
- Image-heavy PDFs can take longer to process because visual extraction and model analysis require additional work and API calls.
- AI-generated summaries, methods, metrics and research interpretations can be incomplete or incorrect. Verify every important claim, quotation, number and page reference in the source PDF.
- Citation-context and paper-to-code analysis are limited to information available in the supplied paper text; the application does not independently verify external repositories or cited publications.
- Local persistence uses SQLite and local files; this version is not a multi-user hosted service.

## Security and repository hygiene

The `.gitignore` excludes local secrets, virtual environments, SQLite databases, uploaded documents, generated caches and local Streamlit secrets. Before pushing, inspect the staged files:

```bash
git status --short
git diff --cached --stat
git diff --cached
```

Do not commit `.env`, `documind.db`, private papers, user uploads or generated personal data.

## License

No license is included in this repository version. Add a license only after choosing the terms under which you want others to use, modify and distribute the project.
