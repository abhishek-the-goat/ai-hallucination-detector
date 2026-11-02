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

# Question patterns
QUESTION_PATTERNS = [
    r"\?+\s*$",
    r"^(?:who|what|where|when|why|how|which|whose|whom|is|are|was|were|do|does|did|can|could|would|should|will)\b.*\?*$"
]

# Emotion and subjective feeling patterns
EMOTION_PATTERNS = [
    r"^(?:i\s+(?:am\s+feeling|feel|am)\s+(?:so\s+|very\s+|really\s+)?(?:sad|happy|angry|depressed|anxious|stressed|excited|lonely|nervous|scared|upset|joyful|exhausted|overwhelmed|heartbroken|furious|mad))\b",
    r"^(?:i\s+(?:love|hate|adore|despise|cherish|fear|dread|miss))\s+(?:it|you|this|that|them|him|her|everything|life)\b",
    r"^(?:this\s+(?:makes\s+me\s+(?:feel\s+)?(?:sad|happy|angry|cry)|hurts|breaks\s+my\s+heart|warms\s+my\s+heart))\b",
    r"^(?:my\s+heart\s+is\s+(?:broken|heavy|full|racing))\b",
]

# Self-referential or conversational dialogue patterns (questions/statements about oneself or the bot)
SELF_REFERENTIAL_PATTERNS = [
    r"^(?:who\s+am\s+i|what\s+am\s+i|why\s+am\s+i\s+here|what\s+is\s+my\s+purpose|who\s+are\s+you|what\s+are\s+you|are\s+you\s+(?:an?\s+)?(?:ai|robot|human|real)|how\s+are\s+you(?:\s+doing)?)\b",
    r"^(?:tell\s+me\s+about\s+yourself|what\s+can\s+you\s+do|what\s+is\s+your\s+name|who\s+(?:made|created)\s+you)\b",
    r"^(?:i\s+am|i'm)\s+(?:tired|bored|hungry|sleepy|lazy|confused|lost|alone|back)\b",
    r"^(?:my\s+name\s+is|my\s+favorite\s+\w+\s+is)\b",
]

# Keyboard smash and gibberish patterns
KEYBOARD_SMASH_PATTERNS = [
    r"(?:qwerty|asdfg|zxcvb|hjkl|yuiop|qwertz|azerty)",
    r"[bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ]{6,}",
    r"(.)\1{3,}",
]

# Common English verbs and predicates for assertion checking
COMMON_VERBS = {
    # Auxiliaries & copulas
    "is", "are", "was", "were", "am", "be", "been", "being",
    "has", "have", "had", "do", "does", "did",
    "can", "could", "will", "would", "shall", "should", "may", "might", "must",
    "become", "became", "becomes", "seem", "seems", "seemed",
    # Common action, state, and scientific/factual verbs
    "won", "win", "wins", "winning", "born", "died", "die", "dies", "dying",
    "lived", "live", "lives", "living", "moved", "move", "moves", "moving",
    "built", "build", "builds", "building", "wrote", "write", "writes", "written", "writing",
    "discovered", "discover", "discovers", "discovering", "invented", "invent", "invents",
    "made", "make", "makes", "making", "created", "create", "creates", "creating",
    "took", "take", "takes", "taken", "taking", "held", "hold", "holds", "holding",
    "found", "find", "finds", "finding", "known", "knew", "know", "knows", "knowing",
    "called", "call", "calls", "calling", "said", "say", "says", "saying",
    "led", "lead", "leads", "leading", "began", "begin", "begins", "beginning",
    "ended", "end", "ends", "ending", "started", "start", "starts", "starting",
    "stopped", "stop", "stops", "stopping", "opened", "open", "opens", "opening",
    "closed", "close", "closes", "closing", "showed", "show", "shows", "shown", "showing",
    "appeared", "appear", "appears", "appearing", "formed", "form", "forms", "forming",
    "served", "serve", "serves", "serving", "joined", "join", "joins", "joining",
    "worked", "work", "works", "working", "played", "play", "plays", "playing",
    "used", "use", "uses", "using", "caused", "cause", "causes", "causing",
    "produced", "produce", "produces", "producing", "contains", "contain", "contained", "containing",
    "provides", "provide", "provides", "providing", "includes", "include", "includes", "including",
    "rules", "rule", "ruled", "ruling", "governed", "govern", "governs", "governing",
    "orbits", "orbit", "orbited", "orbiting", "rotates", "rotate", "rotated", "rotating",
    "boils", "boil", "boiled", "boiling", "melts", "melt", "melted", "melting",
    "freezes", "freeze", "froze", "frozen", "freezing", "flies", "fly", "flew", "flown", "flying",
    "swims", "swim", "swam", "swum", "swimming", "runs", "run", "ran", "running",
    "walks", "walk", "walked", "walking", "eats", "eat", "ate", "eaten", "eating",
    "drinks", "drink", "drank", "drunk", "drinking", "sleeps", "sleep", "slept", "sleeping",
    "breathes", "breathe", "breathed", "breathing", "shines", "shine", "shone", "shining",
    "falls", "fall", "fell", "fallen", "falling", "rises", "rise", "rose", "risen", "rising",
    "flows", "flow", "flowed", "flowing", "burns", "burn", "burned", "burnt", "burning",
    "kills", "kill", "killed", "killing", "destroys", "destroy", "destroyed", "destroying",
    "protects", "protect", "protected", "protecting", "helps", "help", "helped", "helping",
    "hurts", "hurt", "hurting", "costs", "cost", "costing", "pays", "pay", "paid", "paying",
    "sells", "sell", "sold", "selling", "buys", "buy", "bought", "buying",
    "teaches", "teach", "taught", "teaching", "learns", "learn", "learned", "learning",
    "speaks", "speak", "spoke", "spoken", "speaking", "tells", "tell", "told", "telling",
    "reads", "read", "reading", "listens", "listen", "listened", "listening",
    "watches", "watch", "watched", "watching", "sees", "see", "saw", "seen", "seeing",
    "hears", "hear", "heard", "hearing", "feels", "felt", "feeling",
    "located", "situated", "elected", "graduated", "completed", "established", "founded"
}


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


def is_emotion(text: str) -> bool:
    """Check if text expresses personal feelings, emotions, or affective states."""
    cleaned = text.strip().lower()
    for pattern in EMOTION_PATTERNS:
        if re.search(pattern, cleaned):
            return True
    return False


def is_self_referential(text: str) -> bool:
    """Check if text is personal dialogue about oneself or questions directed at the AI/bot."""
    cleaned = text.strip().lower()
    for pattern in SELF_REFERENTIAL_PATTERNS:
        if re.search(pattern, cleaned):
            return True
    return False


def is_single_word(text: str) -> bool:
    """
    Check if the text consists of only a single word or single token.
    A single word cannot form a verifiable factual assertion.
    """
    words = re.findall(r"\b[A-Za-z0-9_'-]+\b", text.strip())
    return len(words) <= 1


def is_random_or_gibberish(text: str) -> bool:
    """
    Check if text is random gibberish, keyboard smashing, symbol spam,
    or non-linguistic noise.
    """
    cleaned = text.strip()
    if not cleaned:
        return True

    letters = re.findall(r"[A-Za-z]", cleaned)
    # If there are no alphabetic letters at all (e.g. '12345678', '... ???')
    if not letters:
        return True

    lower = cleaned.lower()

    # Common keyboard smash patterns
    for pattern in KEYBOARD_SMASH_PATTERNS:
        if re.search(pattern, lower):
            return True

    # Low vowel ratio in alphabetic text of significant length (>= 6 letters)
    if len(letters) >= 6:
        vowels = [c for c in letters if c.lower() in "aeiouy"]
        if (len(vowels) / len(letters)) < 0.15:
            return True

    # Words of 5+ letters with zero vowels (e.g. 'bcdfgh', 'qwrtyp')
    words = re.findall(r"\b[A-Za-z]+\b", lower)
    for w in words:
        if len(w) >= 5 and not any(c in "aeiouy" for c in w):
            return True

    # Repetitive words: e.g. "bla bla bla", "test test test"
    if len(words) >= 3 and len(set(words)) == 1:
        return True

    # High symbol or punctuation ratio (> 50% non-alphanumeric among non-whitespace)
    non_space = [c for c in cleaned if not c.isspace()]
    if non_space:
        symbol_count = sum(1 for c in non_space if not c.isalnum())
        if (symbol_count / len(non_space)) >= 0.5:
            return True

    return False


# Try importing spaCy optionally for robust linguistic assertion checking
try:
    import spacy
    try:
        _nlp = spacy.load("en_core_web_sm")
    except Exception:
        _nlp = None
except ImportError:
    _nlp = None


def has_assertion_predicate(text: str) -> bool:
    """
    Check if the text contains a verb or assertion predicate.
    A valid factual claim must assert something about a subject.
    """
    cleaned = text.strip()
    if not cleaned:
        return False

    if _nlp is not None:
        try:
            doc = _nlp(cleaned)
            if any(token.pos_ in {"VERB", "AUX"} for token in doc):
                return True
        except Exception:
            pass

    words = re.findall(r"\b[A-Za-z]+(?:'[a-z]+)?\b", cleaned.lower())
    if not words:
        return False

    for w in words:
        if w in COMMON_VERBS:
            return True
        # Check standard regular verb inflections (-ed, -ing) with stem length >= 2
        if len(w) >= 4 and (w.endswith("ed") or w.endswith("ing")):
            return True

    return False


def classify_statement(text: str) -> dict:
    """
    Classifies an individual sentence into a category and provides
    a friendly message explaining why it is or is not an objective fact.
    Identifies invalid inputs (single words, random gibberish, verbless phrases)
    without imposing an arbitrary minimum word limit on valid short assertions.
    """
    cleaned = text.strip()
    if not cleaned:
        return {
            "text": text,
            "is_factual_claim": False,
            "category": "EMPTY",
            "message": "Invalid input: Text is empty or blank."
        }

    # 1. Random gibberish, symbol spam, or keyboard smashing
    if is_random_or_gibberish(cleaned):
        return {
            "text": text,
            "is_factual_claim": False,
            "category": "INVALID",
            "message": "Invalid input: Random text, nonsensical characters, or symbol spam detected."
        }

    # 2. Single word (cannot form a verifiable factual assertion or answer)
    if is_single_word(cleaned):
        return {
            "text": text,
            "is_factual_claim": False,
            "category": "INVALID",
            "message": "Invalid input: A single word is not a verifiable factual claim or complete answer."
        }

    # 3. Questions
    if is_question(cleaned):
        if is_self_referential(cleaned):
            return {
                "text": text,
                "is_factual_claim": False,
                "category": "SELF_QUESTION",
                "message": "This is a personal or existential question, not a verifiable factual statement."
            }
        return {
            "text": text,
            "is_factual_claim": False,
            "category": "QUESTION",
            "message": "This is a question asking for information, not a factual claim."
        }

    # 4. Personal emotions & feelings
    if is_emotion(cleaned):
        return {
            "text": text,
            "is_factual_claim": False,
            "category": "EMOTION",
            "message": "This expresses a personal emotion, feeling, or emotional state rather than an objective fact."
        }

    # 5. Self-referential / bot dialogue
    if is_self_referential(cleaned):
        return {
            "text": text,
            "is_factual_claim": False,
            "category": "SELF_REFERENTIAL",
            "message": "This is a personal conversational statement rather than a verifiable public fact."
        }

    # 6. Conversational greetings and fillers
    if is_greeting_or_filler(cleaned):
        return {
            "text": text,
            "is_factual_claim": False,
            "category": "GREETING_FILLER",
            "message": "This is a conversational greeting or polite filler phrase."
        }

    # 7. Recommendations and advice
    if is_recommendation(cleaned):
        return {
            "text": text,
            "is_factual_claim": False,
            "category": "RECOMMENDATION",
            "message": "This is advice, an instruction, or a recommendation rather than a factual statement."
        }

    # 8. Pure subjective opinion
    if is_pure_opinion(cleaned):
        return {
            "text": text,
            "is_factual_claim": False,
            "category": "OPINION",
            "message": "This is a subjective opinion or value judgment without an objective verifiable fact."
        }

    # 9. Verbless / no predicate assertion
    if not has_assertion_predicate(cleaned):
        return {
            "text": text,
            "is_factual_claim": False,
            "category": "INVALID",
            "message": "Invalid input: Statement lacks a verb or factual assertion."
        }

    # 10. Valid factual claim
    return {
        "text": text,
        "is_factual_claim": True,
        "category": "FACTUAL_CLAIM",
        "message": "Checkable factual claim."
    }


def is_valid_factual_claim(text: str) -> bool:
    """
    Applies all filters to ensure the text is a legitimate, standalone,
    checkable factual statement.
    Does NOT impose an arbitrary minimum word count, but rejects single words,
    random gibberish, verbless phrases, and non-claim noise.
    """
    cleaned = text.strip()
    if not cleaned:
        return False

    # Reject single words (must have at least 2 words to form subject + predicate)
    if is_single_word(cleaned):
        return False

    # Reject random gibberish or nonsensical characters
    if is_random_or_gibberish(cleaned):
        return False

    # Reject statements without a verb or predicate
    if not has_assertion_predicate(cleaned):
        return False

    # Reject questions
    if is_question(cleaned):
        return False

    # Reject personal emotions & feelings
    if is_emotion(cleaned):
        return False

    # Reject personal/self-referential dialogue
    if is_self_referential(cleaned):
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
