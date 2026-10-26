"""
Claim Extractor package for AI Hallucination Detector.
Owned by Pratham.
"""

from claim_extractor.extractor import extract_claims, Claim
from claim_extractor.filters import (
    is_valid_factual_claim,
    is_opinion,
    is_question,
    is_greeting_or_filler,
    is_recommendation
)
from claim_extractor.ai_input import get_ai_answer

__all__ = [
    "extract_claims",
    "Claim",
    "get_ai_answer",
    "is_valid_factual_claim",
    "is_opinion",
    "is_question",
    "is_greeting_or_filler",
    "is_recommendation"
]
