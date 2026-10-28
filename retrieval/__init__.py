"""
retrieval package — AI Hallucination Detector
=============================================
Public API:
    retrieve_evidence(claim_text, k=5) -> list[Evidence]

Each Evidence dict contains: text, source_title, source_url, score.

To populate the corpus for the first time run::

    from retrieval.corpus import build_corpus
    build_corpus()
"""

from retrieval.search import retrieve_evidence

__all__ = ["retrieve_evidence"]
