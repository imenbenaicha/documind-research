"""Metadata extraction for scholarly PDFs.

Uses PDF document-info fields first where appropriate, then page-one text.
Only metadata supported by the supplied PDF is returned; absent fields stay empty.
"""
from __future__ import annotations

import re
from pathlib import Path

YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)


def _clean(value: str) -> str:
    value = str(value or "")
    value = value.replace("\ufb01", "fi").replace("\ufb02", "fl")
    value = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", value)
    value = re.sub(r"[\t\r ]+", " ", value)
    value = re.sub(r"\s*\n\s*", " ", value)
    return re.sub(r"\s+", " ", value).strip(" \t\n:;,.|-")


def _page_one(text: str) -> str:
    match = re.search(r"(?im)^\s*\[Page\s+1\]\s*$", text)
    if match:
        tail = text[match.end():]
        next_page = re.search(r"(?im)^\s*\[Page\s+\d+\]\s*$", tail)
        return tail[: next_page.start()] if next_page else tail
    return text


def _author_from_pdf_info(pdf_metadata) -> str:
    raw = str((pdf_metadata or {}).get("/Author", "")).strip()
    if not raw:
        return ""
    names = re.split(r"\s*[;|]\s*", raw)
    names = [_clean(name) for name in names if _clean(name)]
    return ", ".join(names)


def _author_from_first_page(lines: list[str], title: str) -> str:
    """Find the author block between title and the first affiliation/abstract."""
    title_words = set(re.findall(r"[a-z0-9]+", title.lower()))
    title_start = None
    # PDF extraction can wrap a title across adjacent lines. Find the line
    # whose words overlap most with the title, then inspect the next few lines.
    best = (0.0, None)
    for i, line in enumerate(lines[:35]):
        words = set(re.findall(r"[a-z0-9]+", line.lower()))
        if not words:
            continue
        score = len(words & title_words) / max(1, len(words))
        if score > best[0]:
            best = (score, i)
    if best[0] >= 0.45:
        title_start = best[1]

    start = (title_start + 1) if title_start is not None else 0
    author_lines = []
    stop = re.compile(r"abstract|google|university|institute|department|laboratory|@|\b(arxiv|proceedings)\b", re.I)
    for line in lines[start : start + 9]:
        line = _clean(line)
        if not line:
            continue
        if stop.search(line):
            if author_lines:
                break
            continue
        # Reject running headers, dates, page numbers, and long prose.
        if len(line) > 180 or YEAR_RE.search(line) or len(line.split()) > 18:
            continue
        if re.search(r"[A-Z][a-z]+", line) and not re.search(r"[.!?]", line):
            author_lines.append(line)
    return ", ".join(author_lines[:2])


def _extract_abstract(page_text: str) -> str:
    # Restrict extraction to page one: this prevents a later occurrence of
    # "abstract" or unrelated body text from being mistaken for the abstract.
    match = re.search(
        r"(?is)\babstract\b\s*(.*?)(?=\n\s*(?:\d+\s+)?introduction\b|\n\s*1\s+introduction\b)",
        page_text,
    )
    if not match:
        return ""
    abstract = _clean(match.group(1))
    # Avoid returning a truncated fragment if a malformed PDF has no boundary.
    return abstract[:5000]


def extract_metadata(text: str, pdf_metadata=None, filename="paper.pdf") -> dict:
    pdf_metadata = pdf_metadata or {}
    page1 = _page_one(text)
    raw_lines = [line.strip() for line in page1.splitlines() if line.strip()]
    lines = [_clean(line) for line in raw_lines]
    page1_joined = "\n".join(raw_lines)

    pdf_title = _clean(pdf_metadata.get("/Title", ""))
    title = pdf_title if len(pdf_title) > 8 and not pdf_title.lower().endswith(".pdf") else ""
    if not title:
        # In this paper the title is the multi-line block immediately before
        # the author line. Exclude venue/date/page-number headers.
        abstract_index = next((i for i, line in enumerate(lines) if line.lower() == "abstract"), len(lines))
        candidates = []
        for line in lines[:abstract_index]:
            if len(line) < 12 or len(line) > 220:
                continue
            if re.search(r"proceedings of|pages?\s+\d|\b19\d{2}\b|\b20\d{2}\b|@|\bcopyright\b", line, re.I):
                continue
            if re.fullmatch(r"\d+", line):
                continue
            if re.search(r"university|institute|department|laboratory", line, re.I):
                continue
            candidates.append(line)
        if candidates:
            # Use a short consecutive title block, preferring the lines with
            # the greatest title-like length and keeping source order.
            title = _clean(" ".join(candidates[-3:]))

    authors = _author_from_pdf_info(pdf_metadata)
    if not authors:
        authors = _author_from_first_page(lines, title)

    doi_match = DOI_RE.search(page1_joined)
    doi = doi_match.group(0).rstrip(".,);]}") if doi_match else ""
    if not doi:
        info_doi = str(pdf_metadata.get("/Subject", ""))
        doi_match = DOI_RE.search(info_doi)
        doi = doi_match.group(0).rstrip(".,);]}") if doi_match else ""

    year = ""
    venue = ""
    for line in lines[:15]:
        if not year:
            year_match = YEAR_RE.search(line)
            if year_match:
                year = year_match.group(0)
        if not venue and re.search(r"proceedings of|international conference|conference on|journal of|transactions on|workshop on", line, re.I):
            venue = line[:300]

    for source in (str(pdf_metadata.get("/CreationDate", "")), str(pdf_metadata.get("/ModDate", ""))):
        if not year:
            year_match = YEAR_RE.search(source)
            if year_match:
                year = year_match.group(0)

    abstract = _extract_abstract(page1)
    keyword_match = re.search(r"(?im)^\s*(?:keywords?|index terms)\s*[:—-]\s*(.+)$", text)
    keywords = _clean(keyword_match.group(1))[:1000] if keyword_match else _clean(pdf_metadata.get("/Keywords", ""))

    return {
        "title": title or Path(filename).stem,
        "authors": authors,
        "publication_year": year,
        "venue": venue,
        "doi": doi,
        "abstract": abstract,
        "keywords": keywords,
    }
