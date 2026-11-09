"""PDF text extraction and sentence-aware chunking utilities.

Framework-independent utilities reusable by Streamlit and other interfaces.
"""

import re

from pypdf import PdfReader


_ABBREVIATIONS = (
    "a.m.", "p.m.", "e.g.", "i.e.", "etc.", "vs.", "Dr.", "Mr.", "Mrs.",
    "Ms.", "Prof.", "Fig.", "No.",
)


def _split_into_sentences(text):
    """Split extracted page text into sentence-like units.

    Common abbreviations are protected so periods in times such as 8:00 a.m.
    do not create broken sentence boundaries.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    paragraphs = []
    for block in re.split(r"\n\s*\n", text):
        block = re.sub(r"\s*\n\s*", " ", block).strip()
        if block:
            paragraphs.append(block)

    sentences = []
    for paragraph in paragraphs:
        protected = paragraph
        replacements = {}

        for index, abbreviation in enumerate(_ABBREVIATIONS):
            token = f"ZXQABBR{index}ZXQ"
            pattern = re.escape(abbreviation)
            protected, count = re.subn(
                pattern,
                token,
                protected,
                flags=re.IGNORECASE,
            )
            if count:
                replacements[token] = abbreviation

        parts = re.split(r"(?<=[.!?])\s+", protected)

        for part in parts:
            for token, abbreviation in replacements.items():
                part = part.replace(token, abbreviation)
            part = part.strip()
            if part:
                sentences.append(part)

    return sentences


def _make_page_chunks(page_text, chunk_size, overlap):
    """Build page-local chunks, preferring sentence boundaries."""
    sentences = _split_into_sentences(page_text)

    units = []
    for sentence in sentences:
        words = sentence.split()
        if len(words) <= chunk_size:
            units.append(sentence)
        else:
            units.extend(
                " ".join(words[i:i + chunk_size])
                for i in range(0, len(words), chunk_size)
            )

    chunks = []
    current = []
    current_words = 0

    for unit in units:
        unit_words = len(unit.split())

        if current and current_words + unit_words > chunk_size:
            chunks.append(" ".join(current))

            # Carry over whole trailing sentences, up to the requested
            # overlap. Never cut a sentence merely to hit the overlap count.
            carry = []
            carry_words = 0
            for previous in reversed(current):
                count = len(previous.split())
                if carry_words + count > overlap:
                    break
                carry.insert(0, previous)
                carry_words += count

            current = carry
            current_words = carry_words

        current.append(unit)
        current_words += unit_words

    if current:
        final_text = " ".join(current)
        if not chunks or final_text != chunks[-1]:
            chunks.append(final_text)

    return chunks


def extract_chunks(
    pdf_file,
    document_name="document.pdf",
    document_id=None,
    chunk_size=180,
    overlap=25,
):
    """Extract PDF text and split it into sentence-aware chunks.

    Each chunk retains its document identity, filename, page number and type.
    Chunking is performed independently for each page to preserve accurate
    page-level evidence references.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size.")

    reader = PdfReader(pdf_file)
    chunks = []

    for page_number, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        if not page_text.strip():
            continue

        for passage in _make_page_chunks(page_text, chunk_size, overlap):
            if passage.strip():
                chunks.append(
                    {
                        "document_id": document_id,
                        "document_name": document_name,
                        "page": page_number,
                        "text": passage,
                        "type": "text",
                    }
                )

    return chunks