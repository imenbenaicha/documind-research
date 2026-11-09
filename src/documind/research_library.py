"""Persistent paper library for DocuMind Research."""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader
from src.documind.metadata_extraction import extract_metadata

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "documind.db"
PAPER_DIR = PROJECT_ROOT / "data" / "research_library"


def _connect():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_research_schema():
    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS research_papers (
                paper_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                title TEXT NOT NULL,
                authors TEXT DEFAULT '',
                publication_year TEXT DEFAULT '',
                venue TEXT DEFAULT '',
                doi TEXT DEFAULT '',
                abstract TEXT DEFAULT '',
                keywords TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                page_count INTEGER DEFAULT 0,
                text_content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS research_collections (
                collection_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS research_collection_papers (
                collection_id INTEGER NOT NULL,
                paper_id TEXT NOT NULL,
                PRIMARY KEY (collection_id, paper_id),
                FOREIGN KEY(collection_id) REFERENCES research_collections(collection_id)
                    ON DELETE CASCADE,
                FOREIGN KEY(paper_id) REFERENCES research_papers(paper_id)
                    ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS research_analyses (
                analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
                feature TEXT NOT NULL,
                paper_ids TEXT NOT NULL,
                input_hash TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_research_analyses_hash ON research_analyses(feature, input_hash)")


def _extract_pdf_text(pdf_bytes):
    from io import BytesIO
    reader = PdfReader(BytesIO(pdf_bytes))
    pages = []
    for number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(f"[Page {number}]\n{text}")
    return "\n\n".join(pages), len(reader.pages)


def add_paper(pdf_bytes, filename, metadata=None):
    """Store a PDF once by content hash and retain editable metadata."""
    metadata = metadata or {}
    paper_id = hashlib.sha256(pdf_bytes).hexdigest()
    text_content, page_count = _extract_pdf_text(pdf_bytes)
    if not text_content.strip():
        raise ValueError("No selectable text was extracted. OCR support is not yet included in this library importer.")

    safe_name = Path(filename).name
    # Automatically enrich metadata from the first pages and PDF document info.
    from io import BytesIO
    reader = PdfReader(BytesIO(pdf_bytes))
    pdf_info = reader.metadata or {}
    inferred = extract_metadata(text_content, pdf_info, safe_name)
    for key, value in inferred.items():
        if not str(metadata.get(key, "")).strip():
            metadata[key] = value
    stored_path = PAPER_DIR / f"{paper_id}.pdf"
    if not stored_path.exists():
        stored_path.write_bytes(pdf_bytes)

    now = datetime.now(timezone.utc).isoformat()
    title = str(metadata.get("title") or Path(safe_name).stem).strip()
    with _connect() as conn:
        existing = conn.execute("SELECT paper_id FROM research_papers WHERE paper_id=?", (paper_id,)).fetchone()
        if existing:
            # Backfill empty metadata fields for papers already in the library.
            conn.execute("""UPDATE research_papers SET
                title=CASE WHEN title='' OR title=? THEN ? ELSE title END,
                authors=CASE WHEN authors='' THEN ? ELSE authors END,
                publication_year=CASE WHEN publication_year='' THEN ? ELSE publication_year END,
                venue=CASE WHEN venue='' THEN ? ELSE venue END,
                doi=CASE WHEN doi='' THEN ? ELSE doi END,
                abstract=CASE WHEN abstract='' THEN ? ELSE abstract END,
                keywords=CASE WHEN keywords='' THEN ? ELSE keywords END,
                updated_at=? WHERE paper_id=?""", (
                    Path(safe_name).stem, inferred["title"], inferred["authors"],
                    inferred["publication_year"], inferred["venue"], inferred["doi"],
                    inferred["abstract"], inferred["keywords"], now, paper_id
                ))
            return paper_id, False
        conn.execute("""
            INSERT INTO research_papers (
                paper_id, filename, stored_path, title, authors, publication_year,
                venue, doi, abstract, keywords, notes, page_count, text_content,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            paper_id, safe_name, str(stored_path), title,
            str(metadata.get("authors", "")), str(metadata.get("publication_year", "")),
            str(metadata.get("venue", "")), str(metadata.get("doi", "")),
            str(metadata.get("abstract", "")), str(metadata.get("keywords", "")),
            str(metadata.get("notes", "")), page_count, text_content, now, now
        ))
    return paper_id, True


def list_papers():
    with _connect() as conn:
        rows = conn.execute("""
            SELECT paper_id, filename, title, authors, publication_year, venue,
                   doi, abstract, keywords, notes, page_count, created_at
            FROM research_papers ORDER BY updated_at DESC
        """).fetchall()
    return [dict(row) for row in rows]


def get_paper(paper_id):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM research_papers WHERE paper_id=?", (paper_id,)).fetchone()
    return dict(row) if row else None


def update_paper_metadata(paper_id, metadata):
    allowed = ("title", "authors", "publication_year", "venue", "doi", "abstract", "keywords", "notes")
    values = {key: str(metadata.get(key, "")) for key in allowed}
    values["updated_at"] = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute("""
            UPDATE research_papers SET title=:title, authors=:authors,
                publication_year=:publication_year, venue=:venue, doi=:doi,
                abstract=:abstract, keywords=:keywords, notes=:notes,
                updated_at=:updated_at WHERE paper_id=:paper_id
        """, {**values, "paper_id": paper_id})


def delete_paper(paper_id):
    with _connect() as conn:
        row = conn.execute("SELECT stored_path FROM research_papers WHERE paper_id=?", (paper_id,)).fetchone()
        conn.execute("DELETE FROM research_papers WHERE paper_id=?", (paper_id,))
    if row:
        Path(row["stored_path"]).unlink(missing_ok=True)


def create_collection(name, description=""):
    name = name.strip()
    if not name:
        raise ValueError("Collection name cannot be empty.")
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO research_collections(name, description, created_at) VALUES (?, ?, ?)",
            (name, description.strip(), now),
        )
        row = conn.execute("SELECT collection_id FROM research_collections WHERE name=?", (name,)).fetchone()
    return int(row["collection_id"])


def list_collections():
    with _connect() as conn:
        rows = conn.execute("""
            SELECT c.collection_id, c.name, c.description, c.created_at,
                   COUNT(cp.paper_id) AS paper_count
            FROM research_collections c
            LEFT JOIN research_collection_papers cp ON cp.collection_id=c.collection_id
            GROUP BY c.collection_id ORDER BY c.name
        """).fetchall()
    return [dict(row) for row in rows]


def add_paper_to_collection(collection_id, paper_id):
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO research_collection_papers(collection_id, paper_id) VALUES (?, ?)",
            (collection_id, paper_id),
        )


def papers_in_collection(collection_id):
    with _connect() as conn:
        rows = conn.execute("""
            SELECT p.paper_id, p.title, p.filename, p.authors, p.publication_year
            FROM research_papers p
            JOIN research_collection_papers cp ON cp.paper_id=p.paper_id
            WHERE cp.collection_id=? ORDER BY p.title
        """, (collection_id,)).fetchall()
    return [dict(row) for row in rows]


def save_analysis(feature, paper_ids, input_hash, result):
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute("""
            INSERT INTO research_analyses(feature, paper_ids, input_hash, result_json, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (feature, json.dumps(sorted(paper_ids)), input_hash, json.dumps(result, ensure_ascii=False), now))


def get_cached_analysis(feature, input_hash):
    with _connect() as conn:
        row = conn.execute("""
            SELECT result_json FROM research_analyses
            WHERE feature=? AND input_hash=? ORDER BY analysis_id DESC LIMIT 1
        """, (feature, input_hash)).fetchone()
    return json.loads(row["result_json"]) if row else None
