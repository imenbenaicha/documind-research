"""Smoke tests for the first DocuMind Research refactoring step."""

from src.documind.ingestion.pdf_parser import extract_chunks
from src.documind.evidence.highlighting import (
    get_words,
    _split_evidence_sentences,
    _sentence_evidence_score,
)


def test_get_words_removes_common_stop_words():
    assert get_words("The model improves research retrieval") == {
        "model", "improves", "research", "retrieval"
    }


def test_sentence_splitter_returns_sentences():
    assert _split_evidence_sentences("First result. Second result!") == [
        "First result.", "Second result!"
    ]


def test_sentence_evidence_score_rewards_matching_evidence():
    score = _sentence_evidence_score(
        "The model achieved 95% accuracy on the test dataset.",
        "The model achieved 95% accuracy."
    )
    assert score > 0.42


def test_extract_chunks_rejects_invalid_chunk_size():
    try:
        extract_chunks(None, chunk_size=0)
    except ValueError as exc:
        assert "chunk_size" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
