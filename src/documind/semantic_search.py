"""Semantic, BM25, and hybrid retrieval utilities for DocuMind."""

import re
from difflib import SequenceMatcher

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def tokenize(text):
    """Convert text into lowercase tokens."""
    return re.findall(r"\b\w+\b", text.lower())


def _normalize_text(text):
    """Normalize text for duplicate detection without changing source text."""
    return " ".join(tokenize(str(text or "")))


def _same_document(left, right):
    """Avoid deduplicating matching passages from different source documents."""
    keys = ("document_id", "doc_id", "filename", "source", "file_name")
    left_value = next((left.get(key) for key in keys if left.get(key) is not None), None)
    right_value = next((right.get(key) for key in keys if right.get(key) is not None), None)

    # If neither chunk exposes document identity, treat them as belonging
    # to the same retrieval collection.
    if left_value is None or right_value is None:
        return True
    return str(left_value) == str(right_value)


def _is_duplicate(candidate, selected, similarity_threshold=0.88):
    """Return True only when a candidate substantially repeats selected evidence."""
    candidate_text = _normalize_text(candidate.get("text", ""))
    if not candidate_text:
        return True

    candidate_tokens = set(candidate_text.split())

    for existing in selected:
        if not _same_document(candidate, existing):
            continue

        existing_text = _normalize_text(existing.get("text", ""))
        if not existing_text:
            continue

        if candidate_text == existing_text:
            return True

        existing_tokens = set(existing_text.split())
        union = candidate_tokens | existing_tokens
        jaccard = len(candidate_tokens & existing_tokens) / len(union) if union else 1.0

        # Sequence similarity catches near-identical passages with small
        # formatting or extraction differences. Jaccard catches overlapping
        # chunks where one contains a little extra surrounding text.
        sequence_ratio = SequenceMatcher(
            None, candidate_text, existing_text
        ).ratio()

        if jaccard >= similarity_threshold or sequence_ratio >= similarity_threshold:
            return True

    return False


def _deduplicate_ranked_results(results, top_k, similarity_threshold=0.88):
    """Keep the best-ranked distinct passages while preserving original metadata."""
    selected = []

    for result in results:
        if _is_duplicate(result, selected, similarity_threshold):
            continue
        selected.append(result)
        if len(selected) >= top_k:
            break

    return selected


def build_index(chunks):
    """Build semantic and BM25 indexes for all document chunks."""

    if not chunks:
        raise ValueError("Cannot index an empty document collection.")

    texts = [chunk["text"] for chunk in chunks]

    if not any(text.strip() for text in texts):
        raise ValueError("No usable text was found in the documents.")

    model = SentenceTransformer(MODEL_NAME)

    # Semantic index
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    # BM25 keyword index
    tokenized_chunks = [tokenize(text) for text in texts]
    bm25 = BM25Okapi(tokenized_chunks)

    return model, embeddings, bm25


def search(question, chunks, model, embeddings, top_k=5):
    """Retrieve semantically relevant, deduplicated chunks."""

    if not question.strip() or not chunks:
        return []

    query_embedding = model.encode(
        [question],
        normalize_embeddings=True,
    )

    scores = cosine_similarity(
        query_embedding,
        embeddings,
    ).flatten()

    indices = scores.argsort()[::-1]

    ranked = [
        {**chunks[i], "score": float(scores[i])}
        for i in indices
    ]

    return _deduplicate_ranked_results(ranked, top_k=top_k)


def hybrid_search(
    question,
    chunks,
    model,
    embeddings,
    bm25,
    top_k=5,
    semantic_weight=0.5,
    bm25_weight=0.5,
    rrf_k=60,
):
    """
    Combine semantic and keyword rankings using Reciprocal Rank Fusion.

    Deduplication is applied after fusion so the highest-ranked version of
    a repeated passage is retained. Distinct passages from the same page
    remain eligible as separate evidence.
    """

    if not question.strip() or not chunks:
        return []

    # 1. Semantic ranking
    query_embedding = model.encode(
        [question],
        normalize_embeddings=True,
    )

    semantic_scores = cosine_similarity(
        query_embedding,
        embeddings,
    ).flatten()

    semantic_indices = semantic_scores.argsort()[::-1]

    # 2. BM25 keyword ranking
    tokenized_question = tokenize(question)
    bm25_scores = bm25.get_scores(tokenized_question)
    bm25_indices = bm25_scores.argsort()[::-1]

    # 3. Reciprocal Rank Fusion
    fused_scores = {}

    for rank, index in enumerate(semantic_indices, start=1):
        fused_scores[index] = (
            fused_scores.get(index, 0)
            + semantic_weight / (rrf_k + rank)
        )

    for rank, index in enumerate(bm25_indices, start=1):
        fused_scores[index] = (
            fused_scores.get(index, 0)
            + bm25_weight / (rrf_k + rank)
        )

    # 4. Rank every candidate, then remove repeated evidence.
    ranked_indices = sorted(
        fused_scores,
        key=fused_scores.get,
        reverse=True,
    )

    ranked_results = [
        {
            **chunks[index],
            "score": float(fused_scores[index]),
        }
        for index in ranked_indices
    ]

    return _deduplicate_ranked_results(ranked_results, top_k=top_k)


def adaptive_search(
    question,
    chunks,
    model,
    embeddings,
    top_k=5,
    relevance_threshold=0.20,
):
    """Retrieve distinct semantically relevant chunks above a threshold."""

    candidates = search(
        question,
        chunks,
        model,
        embeddings,
        top_k=len(chunks),
    )

    return [
        chunk
        for chunk in candidates
        if chunk["score"] >= relevance_threshold
    ][:top_k]
