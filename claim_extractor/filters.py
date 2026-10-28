"""
Filter module for identifying and removing non-factual sentences (opinions,
greetings, conversational fillers, questions, and recommendations).
Part of the Claim Extractor module owned by Pratham.
"""

import re
from typing import Tuple

# Common conversational fillers and greetings at sentence starts
GREETING_PATTERNS = [
    r"^(?:hello|hi|hey|greetings|good\s+(?:morning|afternoon|evening))\b",
    r"^(?:sure|certainly|of\s+course|absolutely|gladly|happy\s+to\s+help)\b",
    r"^(?:here\s+is|here\s+are|below\s+is|below\s+are|as\s+requested)\b",
    r"^(?:hope\s+this\s+helps|let\s+me\s+know\s+if\s+you\s+need|feel\s+free\s+to\s+ask)\b",
    r"^(?:in\s+conclusion|to\s+summarize|all\s+in\s+all|overall)\b",
]

# Opinion markers and subjective prefixes
OPINION_PREFIX_PATTERNS = [
    r"^(?:i\s+think|i\s+believe|i\s+feel|in\s+my\s+opinion|in\s+my\s+view)\s*,?\s*",
    r"^(?:it\s+seems\s+to\s+me\s+that|it\s+appears\s+that|personally\s*,?\s*i\s+(?:think|believe))\s*",
    r"^(?:from\s+my\s+perspective|as\s+far\s+as\s+i\s+know|to\s+the\s+best\s+of\s+my\s+knowledge)\s*,?\s*",
]

# Subjective adjectives and adverbs indicating pure opinion if not factual
SUBJECTIVE_WORDS = {
    "greatest", "worst", "best", "terrible", "beautiful", "ugly", "amazing",
    "awesome", "horrible", "delicious", "boring", "fascinating", "overrated",
    "underrated", "favorite", "favourite"
}

# Recommendation and advice patterns
RECOMMENDATION_PATTERNS = [
    r"^(?:you\s+should|you\s+ought\s+to|you\s+must|make\s+sure\s+to|be\s+sure\s+to)\b",
    r"^(?:i\s+(?:strongly\s+)?recommend|i\s+advise|it\s+is\s+(?:recommended|advised)\s+to)\b",
    r"^(?:don'?t\s+forget\s+to|always\s+remember\s+to|try\s+to)\b",
]

QUESTION_PATTERNS = [
    r"\?+\s*$",
    r"^(?:who|what|where|when|why|how|which|whose|whom|is|are|was|were|do|does|did|can|could|would|should|will)\b.*\?*$"
]


def is_question(text: str) -> bool:
    """Check if the text is a question."""
    cleaned = text.strip()
    if not cleaned:
        return False
    if cleaned.endswith("?"):
        return True
    
    # Check leading question word combined with question structure
    lower = cleaned.lower()
    for pattern in QUESTION_PATTERNS:
        if re.search(pattern, lower):
            return True
    return False


def is_greeting_or_filler(text: str) -> bool:
    """Check if text is purely a greeting or conversational filler."""
    cleaned = text.strip().lower()
    if not cleaned:
        return True
    
    # Common short conversational tokens
    if cleaned in {"hi", "hello", "hey", "thanks", "thank you", "cheers", "bye", "goodbye"}:
        return True
    
    for pattern in GREETING_PATTERNS:
        if re.search(pattern, cleaned):
            # If it's a short sentence starting with a greeting pattern, it's filler
            if len(cleaned.split()) <= 12:
                return True
    return False


def is_recommendation(text: str) -> bool:
    """Check if text is an imperative recommendation or advisory."""
    cleaned = text.strip().lower()
    for pattern in RECOMMENDATION_PATTERNS:
        if re.search(pattern, cleaned):
            return True
    return False


def strip_opinion_prefix(text: str) -> Tuple[str, bool]:
    """
    Strips subjective hedging prefixes such as 'I think' or 'In my opinion'.
    Returns (cleaned_text, had_opinion_prefix).
    Example:
        'I think Barack Obama was born in 1961' -> ('Barack Obama was born in 1961', True)
    """
    cleaned = text.strip()
    lower = cleaned.lower()
    for pattern in OPINION_PREFIX_PATTERNS:
        match = re.search(pattern, lower)
        if match:
            # Strip matched prefix
            end_idx = match.end()
            remaining = cleaned[end_idx:].strip()
            # Capitalize first letter of remaining text
            if remaining:
                remaining = remaining[0].upper() + remaining[1:]
            return remaining, True
    return cleaned, False


def is_pure_opinion(text: str) -> bool:
    """
    Checks if a sentence is a pure subjective value judgment with no checkable fact.
    Example: 'Pizza is the most delicious food on earth.' -> True
    """
    cleaned = text.strip().lower()
    words = set(re.findall(r"\b\w+\b", cleaned))
    
    # Check if sentence contains strong subjective sentiment words without objective assertions
    has_subjective = bool(words & SUBJECTIVE_WORDS)
    is_copula_subjective = bool(re.search(r"\b(?:is|are|was|were)\s+(?:the\s+)?(?:best|worst|greatest|most\s+\w+)\b", cleaned))
    
    return is_copula_subjective or (has_subjective and len(words) < 8)


def is_opinion(text: str) -> bool:
    """Check if text expresses a subjective opinion or value judgment."""
    return is_pure_opinion(text)


def is_valid_factual_claim(text: str) -> bool:
    """
    Applies all filters to ensure the text is a legitimate, standalone,
    checkable factual statement.
    """
    cleaned = text.strip()
    if not cleaned:
        return False
    
    # Must have a minimum length (e.g. at least 3 words: Subject, Verb, Object)
    tokens = cleaned.split()
    if len(tokens) < 3:
        return False
    
    # Reject questions
    if is_question(cleaned):
        return False
    
    # Reject greetings and filler
    if is_greeting_or_filler(cleaned):
        return False
    
    # Reject recommendations
    if is_recommendation(cleaned):
        return False
    
    # Reject pure opinion / subjective claims
    if is_pure_opinion(cleaned):
        return False
    
    return True
