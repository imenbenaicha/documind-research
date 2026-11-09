
"""Conservative alignment of retrieved PDF evidence to visible PDF words."""
from __future__ import annotations

import re
import fitz
from difflib import SequenceMatcher


def _normalize(text):
    text = str(text or "").lower()
    return (
        text.replace("\ufb01", "fi")
        .replace("\ufb02", "fl")
        .replace("\u2010", "-")
        .replace("\u2011", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )


def _tokens(text):
    return re.findall(r"[a-z0-9]+", _normalize(text))


def _highlight_tokens(text):
    """Backward-compatible helper used by Papers_Discussions.py."""
    return _tokens(text)


def get_words(text):
    stop_words = {
        "the", "a", "an", "is", "was", "were", "are",
        "what", "which", "who", "when", "where", "how",
        "of", "in", "on", "at", "to", "for", "from",
        "and", "or", "with", "by", "did", "does", "do",
        "company", "document", "report",
    }
    return {
        word for word in _tokens(text)
        if len(word) > 1 and word not in stop_words
    }


def apply_green_highlights(page, highlighted_items):
    unique = []
    seen = set()

    for item in highlighted_items:
        rect = (
            fitz.Rect(item.rect)
            if hasattr(item, "rect")
            else fitz.Rect(item)
        )

        key = tuple(
            round(value, 1)
            for value in (rect.x0, rect.y0, rect.x1, rect.y1)
        )

        if rect.is_empty or key in seen:
            continue

        seen.add(key)
        unique.append(rect)

    count = 0

    for rect in unique:
        annot = page.add_highlight_annot(rect)

        if annot:
            annot.set_colors(stroke=(0.2, 0.85, 0.2))
            annot.set_opacity(0.35)
            annot.update()
            count += 1

    return count


def _merge_rects(rects, y_tolerance=3.0):
    if not rects:
        return []

    ordered = sorted(
        (fitz.Rect(rect) for rect in rects),
        key=lambda rect: (
            round(rect.y0 / y_tolerance),
            rect.x0,
        ),
    )

    merged = []

    for rect in ordered:
        if (
            merged
            and abs(rect.y0 - merged[-1].y0) <= y_tolerance
            and rect.x0 - merged[-1].x1 <= 5
        ):
            merged[-1] |= rect
        else:
            merged.append(rect)

    return merged


def _find_token_spans(page_tokens, target_tokens):
    if not page_tokens or not target_tokens:
        return []

    matcher = SequenceMatcher(
        None,
        target_tokens,
        page_tokens,
        autojunk=False,
    )

    blocks = [
        block
        for block in matcher.get_matching_blocks()
        if block.size >= 5
    ]

    covered = sum(block.size for block in blocks)
    coverage = covered / max(1, len(target_tokens))

    if covered < 5 or coverage < 0.45:
        return []

    return [
        (block.b, block.b + block.size)
        for block in blocks
    ]


def _split_evidence_sentences(text):
    normalized = str(text or "").replace("\r", "\n")

    # Repair words split by line-end hyphens.
    normalized = re.sub(
        r"(?<=\w)-\s*\n\s*(?=\w)",
        "",
        normalized,
    )

    # Join PDF line breaks.
    normalized = re.sub(
        r"\s*\n\s*",
        " ",
        normalized,
    )

    parts = re.split(
        r"(?<=[.!?])\s+",
        normalized,
    )

    return [
        part.strip(" \t•-*")
        for part in parts
        if part.strip(" \t•-*")
    ]


def _sentence_evidence_score(source_sentence, answer_sentence):
    source = get_words(source_sentence)
    answer = get_words(answer_sentence)

    if len(source) < 4 or len(answer) < 3:
        return 0.0

    shared = source & answer

    if len(shared) < 3:
        return 0.0

    overlap = len(shared) / min(len(source), len(answer))

    source_numbers = set(
        re.findall(r"\d+(?:[.,]\d+)?%?", source_sentence)
    )

    answer_numbers = set(
        re.findall(r"\d+(?:[.,]\d+)?%?", answer_sentence)
    )

    if (
        source_numbers
        and answer_numbers
        and not (source_numbers & answer_numbers)
    ):
        return 0.0

    return overlap


def highlight_normal_text(page, passage, question="", answer=""):
    """Highlight source sentences that support individual answer facts."""

    source_sentences = _split_evidence_sentences(passage)
    answer_sentences = _split_evidence_sentences(answer)

    if not source_sentences or not answer_sentences:
        return 0

    candidates = []

    for source_sentence in source_sentences:
        score = max(
            (
                _sentence_evidence_score(source_sentence, answer)
                for answer in answer_sentences
            ),
            default=0.0,
        )

        if score >= 0.38:
            candidates.append((score, source_sentence))

    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    if not candidates:
        return 0

    pdf_words = page.get_text("words", sort=False)

    page_tokens = []
    token_rects = []

    for word in pdf_words:
        for token in _tokens(word[4]):
            page_tokens.append(token)
            token_rects.append(fitz.Rect(word[:4]))

    if not page_tokens:
        return 0

    selected_rects = []
    selected_signatures = set()

    for _, sentence in candidates[:3]:
        target_tokens = _tokens(sentence)

        spans = _find_token_spans(
            page_tokens,
            target_tokens,
        )

        for start, end in spans:
            signature = (start, end)

            if signature in selected_signatures:
                continue

            selected_signatures.add(signature)
            selected_rects.extend(token_rects[start:end])

    # Retry using geometry-sorted PDF words if necessary.
    if not selected_rects:
        pdf_words = page.get_text("words", sort=True)

        page_tokens = []
        token_rects = []

        for word in pdf_words:
            for token in _tokens(word[4]):
                page_tokens.append(token)
                token_rects.append(fitz.Rect(word[:4]))

        for _, sentence in candidates[:3]:
            spans = _find_token_spans(
                page_tokens,
                _tokens(sentence),
            )

            for start, end in spans:
                selected_rects.extend(
                    token_rects[start:end]
                )

    if not selected_rects:
        return 0

    merged_rects = _merge_rects(selected_rects)

    return apply_green_highlights(
        page,
        merged_rects,
    )


def highlight_table_evidence(page, question, passage, answer=""):
    """Do not guess table coordinates."""
    return 0


def highlight_passage(page, passage, question="", answer=""):
    try:
        return highlight_normal_text(
            page,
            passage,
            question,
            answer,
        )
    except Exception as error:
        print(f"Evidence highlighting error: {error}")
        return 0
