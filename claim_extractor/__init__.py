"""
Claim Extractor package for AI Hallucination Detector.
Owned by Pratham.
"""

from claim_extractor.extractor import extract_claims, analyze_claims, Claim
from claim_extractor.filters import (
    is_valid_factual_claim,
    is_opinion,
    is_question,
    is_greeting_or_filler,
    is_recommendation,
    is_emotion,
    is_self_referential,
    is_single_word,
    is_random_or_gibberish,
    has_assertion_predicate,
    classify_statement
)
from claim_extractor.ai_input import get_ai_answer

__all__ = [
    "extract_claims",
    "analyze_claims",
    "Claim",
    "get_ai_answer",
    "is_valid_factual_claim",
    "is_opinion",
    "is_question",
    "is_greeting_or_filler",
    "is_recommendation",
    "is_emotion",
    "is_self_referential",
    "is_single_word",
    "is_random_or_gibberish",
    "has_assertion_predicate",
    "classify_statement"
]
