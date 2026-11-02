"""
retrieval/index.py
------------------
Builds and exposes BM25 and FAISS vector indexes over the Document corpus.

Design
------
- BM25Index  : wraps rank-bm25's BM25Okapi for keyword/TF-IDF search.
- VectorIndex: encodes passages with `all-MiniLM-L6-v2` via sentence-transformers,
               stores L2-normalised embeddings in a FAISS IndexFlatIP so that
               inner product == cosine similarity.

Both classes are instantiated through module-level lazy singletons.
Nothing is loaded until `get_indexes()` is called for the first time.
"""

from __future__ import annotations

import re
from typing import Optional

import numpy as np

from retrieval.corpus import Document, load_corpus

# ---------------------------------------------------------------------------
# BM25 Index
# ---------------------------------------------------------------------------


def _tokenise(text: str) -> list[str]:
    """Lower-case, strip punctuation, split on whitespace."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return text.split()


class BM25Index:
    """
    Keyword search index built from a list of Documents using BM25Okapi.

    Parameters
    ----------
    documents : list of Document objects (must be non-empty).
    """

    def __init__(self, documents: list[Document]) -> None:
        if not documents:
            raise ValueError("BM25Index requires a non-empty document list.")

        try:
            from rank_bm25 import BM25Okapi
        except ImportError as exc:
            raise ImportError(
                "rank-bm25 is required. Install it with: pip install rank-bm25"
            ) from exc

        self._docs = documents
        tokenised = [_tokenise(d.text) for d in documents]
        self._bm25 = BM25Okapi(tokenised)

    def search(self, query: str, k: int) -> list[tuple[float, Document]]:
        """
        Return the top-*k* (score, Document) pairs for *query*.

        Scores are raw BM25 values (non-negative floats).
        Results are sorted descending by score.
        """
        if not query or not query.strip():
            return []

        tokens = _tokenise(query)
        scores: np.ndarray = self._bm25.get_scores(tokens)

        # Pair scores with documents and sort
        paired = list(zip(scores.tolist(), self._docs))
        paired.sort(key=lambda x: x[0], reverse=True)
        return paired[:k]


# ---------------------------------------------------------------------------
# Vector Index
# ---------------------------------------------------------------------------

_EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


class VectorIndex:
    """
    Semantic search index built from a list of Documents.

    Embeddings are produced by `all-MiniLM-L6-v2` (sentence-transformers).
    Vectors are L2-normalised before being stored in a FAISS IndexFlatIP so
    that inner-product search == cosine similarity in [0, 1].

    Parameters
    ----------
    documents : list of Document objects (must be non-empty).
    """

    def __init__(self, documents: list[Document]) -> None:
        if not documents:
            raise ValueError("VectorIndex requires a non-empty document list.")

        try:
            import faiss
        except ImportError as exc:
            raise ImportError(
                "faiss-cpu is required. Install it with: pip install faiss-cpu"
            ) from exc

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is required. "
                "Install it with: pip install sentence-transformers"
            ) from exc

        self._docs = documents

        print(f"[index] Loading embedding model '{_EMBEDDING_MODEL_NAME}'…")
        model = SentenceTransformer(_EMBEDDING_MODEL_NAME, device="cpu")

        print(f"[index] Encoding {len(documents)} passages…")
        texts = [d.text for d in documents]
        embeddings: np.ndarray = model.encode(
            texts,
            batch_size=64,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,   # L2-normalise → cosine via dot product
        )
        embeddings = embeddings.astype(np.float32)

        dim = embeddings.shape[1]
        self._index = faiss.IndexFlatIP(dim)
        self._index.add(embeddings)

        # Keep model for query encoding
        self._model = model
        print("[index] VectorIndex ready.")

    def search(self, query: str, k: int) -> list[tuple[float, Document]]:
        """
        Return the top-*k* (cosine_score, Document) pairs for *query*.

        Scores are cosine similarities in [0, 1].
        Results are sorted descending by score.
        """
        if not query or not query.strip():
            return []

        q_emb: np.ndarray = self._model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype(np.float32)

        k_safe = min(k, self._index.ntotal)
        distances, indices = self._index.search(q_emb, k_safe)

        results: list[tuple[float, Document]] = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0:
                continue
            score = float(np.clip(dist, 0.0, 1.0))
            results.append((score, self._docs[idx]))

        results.sort(key=lambda x: x[0], reverse=True)
        return results


# ---------------------------------------------------------------------------
# Lazy module-level singletons
# ---------------------------------------------------------------------------

_bm25_index: Optional[BM25Index] = None
_vector_index: Optional[VectorIndex] = None


def get_indexes(
    documents: Optional[list[Document]] = None,
) -> tuple[BM25Index, VectorIndex]:
    """
    Return the (BM25Index, VectorIndex) singletons, building them on first call.

    Parameters
    ----------
    documents : optional pre-loaded list of Documents.
                If None, the corpus is loaded from the default corpus path.

    Raises
    ------
    RuntimeError  : if the corpus is empty (no passages to index).
    ImportError   : if required packages are missing.
    """
    global _bm25_index, _vector_index

    if _bm25_index is None or _vector_index is None:
        if documents is None:
            documents = load_corpus()

        if not documents:
            raise RuntimeError(
                "The corpus is empty. Run retrieval.corpus.build_corpus() first "
                "to download Wikipedia articles and populate the corpus file."
            )

        print(f"[index] Building indexes from {len(documents)} passages…")
        _bm25_index = BM25Index(documents)
        _vector_index = VectorIndex(documents)
        print("[index] All indexes ready.")

    return _bm25_index, _vector_index


def reset_indexes() -> None:
    """
    Discard the cached index singletons.

    Useful in tests or when the corpus is updated and indexes need rebuilding.
    """
    global _bm25_index, _vector_index
    _bm25_index = None
    _vector_index = None
