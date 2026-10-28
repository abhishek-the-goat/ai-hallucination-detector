"""
retrieval/search.py
-------------------
Public API for the retrieval engine.

Exposes a single entry point:

    retrieve_evidence(claim_text, k=5) -> list[Evidence]

Hybrid retrieval strategy
--------------------------
1. Run BM25 search  → top-k keyword candidates.
2. Run vector search → top-k semantic candidates.
3. Union both result sets (deduplicate by document id).
4. Compute a combined score:
       combined = BM25_WEIGHT * bm25_normalised + VECTOR_WEIGHT * cosine_score
   where bm25_normalised = raw_bm25 / max_raw_bm25  (range [0, 1]).
5. Sort combined candidates descending, return the best k as Evidence dicts.

Nothing in this module triggers a model load or network call on import.
"""

from __future__ import annotations

from typing import Optional

from retrieval.corpus import Document, load_corpus
from retrieval.index import BM25Index, VectorIndex, get_indexes, reset_indexes

# ---------------------------------------------------------------------------
# Score-mixing weights  (must sum to 1.0)
# ---------------------------------------------------------------------------

BM25_WEIGHT: float = 0.40
VECTOR_WEIGHT: float = 0.60

# ---------------------------------------------------------------------------
# Evidence type alias (plain dict to match verification.engine contract)
# ---------------------------------------------------------------------------

# Evidence = {
#   "text":         str,
#   "source_title": str,
#   "source_url":   str,
#   "score":        float,   # combined retrieval score in [0.0, 1.0]
# }
Evidence = dict


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalise_bm25_scores(
    results: list[tuple[float, Document]],
) -> dict[str, float]:
    """
    Map document id → normalised BM25 score in [0, 1].

    The max raw score in the result set is used as the divisor.
    If every score is 0, all normalised scores are 0.
    """
    if not results:
        return {}
    max_score = max(score for score, _ in results)
    if max_score == 0.0:
        return {doc.id: 0.0 for _, doc in results}
    return {doc.id: score / max_score for score, doc in results}


def _merge_results(
    bm25_results: list[tuple[float, Document]],
    vector_results: list[tuple[float, Document]],
) -> list[tuple[float, Document]]:
    """
    Merge BM25 and vector results into a single ranked list.

    - Normalise BM25 scores to [0, 1].
    - Cosine scores from the vector index are already in [0, 1].
    - For documents in both sets, combined = BM25_WEIGHT * bm25_norm
                                           + VECTOR_WEIGHT * cosine.
    - For documents in only one set, the missing score defaults to 0.
    - Returns a list of (combined_score, Document) sorted descending.
    """
    bm25_norm = _normalise_bm25_scores(bm25_results)
    vector_scores: dict[str, float] = {doc.id: score for score, doc in vector_results}

    # Collect all seen documents keyed by id
    all_docs: dict[str, Document] = {}
    for _, doc in bm25_results:
        all_docs[doc.id] = doc
    for _, doc in vector_results:
        all_docs[doc.id] = doc

    merged: list[tuple[float, Document]] = []
    for doc_id, doc in all_docs.items():
        b_score = bm25_norm.get(doc_id, 0.0)
        v_score = vector_scores.get(doc_id, 0.0)
        combined = BM25_WEIGHT * b_score + VECTOR_WEIGHT * v_score
        merged.append((combined, doc))

    merged.sort(key=lambda x: x[0], reverse=True)
    return merged


def _doc_to_evidence(doc: Document, score: float) -> Evidence:
    """Convert a Document + score into the Evidence contract dict."""
    return {
        "text":         doc.text,
        "source_title": doc.source_title,
        "source_url":   doc.source_url,
        "score":        round(float(score), 6),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def retrieve_evidence(
    claim_text: str,
    k: int = 5,
    *,
    _documents: Optional[list[Document]] = None,
    _bm25: Optional[BM25Index] = None,
    _vector: Optional[VectorIndex] = None,
) -> list[Evidence]:
    """
    Retrieve the top-k evidence passages relevant to *claim_text*.

    Parameters
    ----------
    claim_text : The factual claim to search evidence for.
    k          : Maximum number of Evidence dicts to return. Must be >= 1.
                 Values <= 0 are treated as 1.

    Private parameters (for testing / dependency injection only)
    -------------------------------------------------------------
    _documents : pre-loaded Document list (bypasses corpus.load_corpus).
    _bm25      : pre-built BM25Index instance (bypasses singleton).
    _vector    : pre-built VectorIndex instance (bypasses singleton).

    Returns
    -------
    list of Evidence dicts, each with keys:
        text, source_title, source_url, score

    - At most *k* results are returned.
    - Results are sorted by combined score descending.
    - Returns [] for blank claims, invalid k, or an empty corpus.
    - Never fabricates evidence; only real corpus passages are returned.

    Raises
    ------
    RuntimeError : if the corpus is empty and no indexes can be built.
    """
    # --- Guard: blank claim ---
    if not claim_text or not claim_text.strip():
        return []

    # --- Guard: k ---
    k = max(1, int(k))

    # --- Obtain indexes ---
    if _bm25 is not None and _vector is not None:
        bm25_idx, vector_idx = _bm25, _vector
    else:
        try:
            bm25_idx, vector_idx = get_indexes(documents=_documents)
        except RuntimeError:
            # Corpus is empty — return no evidence rather than crashing
            return []

    # --- Search both indexes ---
    bm25_results   = bm25_idx.search(claim_text, k=k)
    vector_results = vector_idx.search(claim_text, k=k)

    # --- Merge, deduplicate, rank ---
    merged = _merge_results(bm25_results, vector_results)

    # --- Build Evidence list ---
    evidence: list[Evidence] = [
        _doc_to_evidence(doc, score)
        for score, doc in merged[:k]
    ]

    return evidence
