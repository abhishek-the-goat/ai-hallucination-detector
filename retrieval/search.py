"""
retrieval/search.py
-------------------
Public API for the multi-source retrieval engine.

Exposes a single entry point:

    retrieve_evidence(claim_text, k=5, sources=("wikipedia", "wikidata", "arxiv")) -> list[Evidence]

Multi-source hybrid retrieval strategy
--------------------------------------
1. Query all enabled sources:
   - Wikipedia: Live Wikipedia (MediaWiki API) + static 390-passage corpus.
   - Wikidata: Structured entity facts (wbsearchentities + Special:EntityData).
   - arXiv: Scientific research papers (export.arxiv.org Atom API).
2. Merge results across all sources.
3. Deduplicate by normalised lowercased text.
4. Re-rank with the existing fusion formula (0.40 BM25 + 0.60 cosine) computed
   over the merged pool.
5. Return top k evidence dicts with contract keys {"text", "source_title", "source_url", "score"}
   plus the "source" field kept.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from retrieval.corpus import Document, load_corpus
from retrieval.index import BM25Index, VectorIndex, _tokenise, get_indexes, reset_indexes

# ---------------------------------------------------------------------------
# Score-mixing weights (must sum to 1.0)
# ---------------------------------------------------------------------------

BM25_WEIGHT: float = 0.40
VECTOR_WEIGHT: float = 0.60

DEFAULT_SOURCES: Tuple[str, ...] = ("wikipedia", "wikidata", "arxiv")

# ---------------------------------------------------------------------------
# Evidence type alias (plain dict to match verification.engine contract)
# ---------------------------------------------------------------------------

Evidence = dict


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalise_bm25_scores(
    results: list[tuple[float, Document]],
) -> dict[str, float]:
    """
    Map document id -> normalised BM25 score in [0, 1].

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


def _doc_to_evidence(
    doc: Document,
    score: float,
    raw_similarity: Optional[float] = None,
    source: str = "wikipedia",
) -> Evidence:
    """Convert a Document + score into the Evidence contract dict."""
    raw_sim = score if raw_similarity is None else raw_similarity
    return {
        "text":              doc.text,
        "source_title":      doc.source_title,
        "source_url":        doc.source_url,
        "score":             round(float(score), 6),
        "raw_similarity":    round(float(raw_sim), 6),
        "cosine_similarity": round(float(raw_sim), 6),
        "source":            source,
    }


def _rerank_merged_pool(
    claim_text: str,
    candidates: List[Evidence],
    k: int = 5,
) -> List[Evidence]:
    """Re-rank candidate evidence with 0.40 normalised BM25 + 0.60 cosine similarity."""
    if not candidates:
        return []

    # Compute BM25 over the merged pool
    norm_bm25: List[float] = []
    try:
        from rank_bm25 import BM25Okapi
        tokenised_corpus = [_tokenise(ev["text"]) for ev in candidates]
        bm25_model = BM25Okapi(tokenised_corpus)
        query_tokens = _tokenise(claim_text)
        raw_bm25_scores = bm25_model.get_scores(query_tokens)
        max_bm25 = float(max(raw_bm25_scores)) if len(raw_bm25_scores) > 0 else 0.0
        if max_bm25 > 0.0:
            norm_bm25 = [float(s) / max_bm25 for s in raw_bm25_scores]
        else:
            norm_bm25 = [0.0 for _ in raw_bm25_scores]
    except Exception:
        norm_bm25 = [0.0 for _ in candidates]

    # Compute cosine similarities
    cosine_scores: List[float] = []
    try:
        from retrieval.live_search import _get_embedding_model
        model = _get_embedding_model()
        q_emb = model.encode([claim_text], convert_to_numpy=True, normalize_embeddings=True)[0]
        p_texts = [ev["text"] for ev in candidates]
        p_embs = model.encode(p_texts, batch_size=32, convert_to_numpy=True, normalize_embeddings=True)
        cosine_scores = np.dot(p_embs, q_emb).tolist()
    except Exception:
        for ev in candidates:
            sim = ev.get("cosine_similarity", ev.get("raw_similarity", ev.get("score")))
            cosine_scores.append(float(sim) if sim is not None else 0.5)

    # Combine using 0.40 BM25 + 0.60 Cosine
    reranked: List[Evidence] = []
    for i, ev in enumerate(candidates):
        b_val = norm_bm25[i] if i < len(norm_bm25) else 0.0
        c_val = max(0.0, min(1.0, float(cosine_scores[i]))) if i < len(cosine_scores) else 0.5
        combined = BM25_WEIGHT * b_val + VECTOR_WEIGHT * c_val

        item = dict(ev)
        item["score"] = round(float(combined), 6)
        item["raw_similarity"] = round(float(c_val), 6)
        item["cosine_similarity"] = round(float(c_val), 6)
        if "source" not in item:
            item["source"] = "wikipedia"
        reranked.append(item)

    reranked.sort(key=lambda x: x["score"], reverse=True)
    return reranked[:k]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def retrieve_evidence(
    claim_text: str,
    k: int = 5,
    live: bool = True,
    sources: Tuple[str, ...] = DEFAULT_SOURCES,
    *,
    _documents: Optional[list[Document]] = None,
    _bm25: Optional[BM25Index] = None,
    _vector: Optional[VectorIndex] = None,
) -> list[Evidence]:
    """
    Retrieve the top-k evidence passages relevant to *claim_text* across enabled sources.

    Parameters
    ----------
    claim_text : The factual claim to search evidence for.
    k          : Maximum number of Evidence dicts to return. Must be >= 1.
                 Values <= 0 are treated as 1.
    live       : If True, query live multi-source retrieval (Wikipedia, Wikidata, arXiv).
                 If False, query only the static offline corpus index.
                 Defaults to True.
    sources    : Enabled evidence sources, subset of ("wikipedia", "wikidata", "arxiv").
                 Defaults to all three.

    Private parameters (for testing / dependency injection only)
    -------------------------------------------------------------
    _documents : pre-loaded Document list (bypasses corpus.load_corpus).
    _bm25      : pre-built BM25Index instance (bypasses singleton).
    _vector    : pre-built VectorIndex instance (bypasses singleton).

    Returns
    -------
    list of Evidence dicts, each with keys:
        text, source_title, source_url, score, raw_similarity, cosine_similarity, source
    """
    # --- Guard: blank claim ---
    if not claim_text or not claim_text.strip():
        return []

    # --- Guard: k ---
    k = max(1, int(k))

    # --- 1. Dependency injection / offline static-only index hook for unit tests ---
    if _bm25 is not None and _vector is not None:
        bm25_results = _bm25.search(claim_text, k=k)
        vector_results = _vector.search(claim_text, k=k)
        merged = _merge_results(bm25_results, vector_results)
        vector_scores: dict[str, float] = {doc.id: score for score, doc in vector_results}
        evidence: list[Evidence] = [
            _doc_to_evidence(doc, score, raw_similarity=vector_scores.get(doc.id, 0.0), source="wikipedia")
            for score, doc in merged[:k]
        ]
        return evidence

    if _documents is not None and not _documents:
        # Explicit empty corpus injected
        return []

    candidate_pool: List[Evidence] = []
    enabled_sources = set(s.lower() for s in sources)

    # --- 2. Wikipedia: static corpus part of the pool ---
    if "wikipedia" in enabled_sources:
        try:
            bm25_idx, vector_idx = get_indexes(documents=_documents)
            bm25_results = bm25_idx.search(claim_text, k=k)
            vector_results = vector_idx.search(claim_text, k=k)
            merged = _merge_results(bm25_results, vector_results)
            vector_scores = {doc.id: score for score, doc in vector_results}
            for score, doc in merged[:k]:
                candidate_pool.append(
                    _doc_to_evidence(doc, score, raw_similarity=vector_scores.get(doc.id, 0.0), source="wikipedia")
                )
        except Exception:
            pass

    # --- 3. Live sources: Wikipedia (MediaWiki), Wikidata, arXiv ---
    if live:
        from retrieval.sources import fetch_wikipedia, fetch_wikidata, fetch_arxiv

        if "wikipedia" in enabled_sources:
            wiki_live = fetch_wikipedia(claim_text, k=k)
            candidate_pool.extend(wiki_live)

        if "wikidata" in enabled_sources:
            wikidata_items = fetch_wikidata(claim_text, k=k)
            candidate_pool.extend(wikidata_items)

        if "arxiv" in enabled_sources:
            arxiv_items = fetch_arxiv(claim_text, k=k)
            candidate_pool.extend(arxiv_items)

    if not candidate_pool:
        return []

    # --- 4. Deduplicate by normalised lowercased text ---
    seen_texts: set[str] = set()
    deduped_candidates: List[Evidence] = []
    for ev in candidate_pool:
        raw_t = ev.get("text", "")
        norm = " ".join(raw_t.strip().lower().split())
        if norm and norm not in seen_texts:
            seen_texts.add(norm)
            deduped_candidates.append(ev)

    # --- 5. Re-rank with 0.40 BM25 + 0.60 Cosine fusion computed over the merged pool ---
    return _rerank_merged_pool(claim_text, deduped_candidates, k=k)
