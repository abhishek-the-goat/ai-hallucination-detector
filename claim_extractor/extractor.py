"""
Claim Extractor Module: Decomposes AI answers into atomic, decontextualized,
and checkable factual claims.
Part of the Claim Extractor module owned by Pratham.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple

from claim_extractor.filters import (
    is_valid_factual_claim,
    strip_opinion_prefix,
    classify_statement
)

logger = logging.getLogger(__name__)

# Try importing spaCy; if not installed or model missing, fallback gracefully
try:
    import spacy
    try:
        nlp = spacy.load("en_core_web_sm")
    except Exception:
        nlp = None
except ImportError:
    spacy = None
    nlp = None

# Typed schema definition
Claim = Dict[str, Any]

# Common abbreviations to prevent false sentence breaks in regex fallback
ABBREVIATIONS = (
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "vs", "inc", "ltd", "corp",
    "u.s", "u.k", "e.g", "i.e", "approx", "dept", "vol", "no", "gen", "rep", "sen"
)

PRONOUN_MAP = {
    "he": "MASCULINE",
    "him": "MASCULINE",
    "his": "MASCULINE",
    "she": "FEMININE",
    "her": "FEMININE",
    "hers": "FEMININE",
    "it": "NEUTER",
    "its": "NEUTER",
    "they": "PLURAL",
    "them": "PLURAL",
    "their": "PLURAL",
    "theirs": "PLURAL"
}


def _split_into_sentences_regex(text: str) -> List[str]:
    """Fallback rule-based sentence segmentation with abbreviation awareness."""
    # Normalize whitespace and newlines
    text = re.sub(r"\r\n|\r|\n", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    # Regex splitting on punctuation followed by space and capital letter
    potential_sents = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
    sentences = []
    buffer = ""

    for s in potential_sents:
        if buffer:
            buffer += " " + s
        else:
            buffer = s

        # Check if the split happened on an abbreviation
        last_word = buffer.rstrip(".!?").split()[-1].lower() if buffer.split() else ""
        if last_word in ABBREVIATIONS:
            continue
        
        sentences.append(buffer.strip())
        buffer = ""

    if buffer:
        sentences.append(buffer.strip())

    return [s for s in sentences if s]


def _split_compound_sentence(sentence: str) -> List[str]:
    """
    Splits compound sentences joined by coordinating conjunctions (and, but, while)
    into single-fact statements if both sides contain a subject and predicate.
    """
    sentence = sentence.strip()
    if not sentence:
        return []

    # If spaCy is loaded, use dependency parse to identify conjoined clauses
    if nlp is not None:
        try:
            doc = nlp(sentence)
            # Find coordinating conjunctions that join clauses
            split_points = []
            for token in doc:
                if token.pos_ == "CCONJ" and token.text.lower() in {"and", "but", "while", "whereas"}:
                    # Check if the conjoined token is a root or clausal predicate
                    head = token.head
                    if head.pos_ == "VERB" and any(child.dep_ in {"conj"} for child in head.children):
                        split_points.append(token.idx)
            
            if split_points:
                clauses = []
                last_idx = 0
                for sp in split_points:
                    clause = sentence[last_idx:sp].strip(" ,")
                    if clause:
                        clauses.append(clause)
                    last_idx = sp
                remaining = sentence[last_idx:].strip(" ,")
                # Remove the leading conjunction in the second clause
                remaining = re.sub(r"^(?:and|but|while|whereas)\s+", "", remaining, flags=re.IGNORECASE)
                if remaining:
                    clauses.append(remaining)
                if len(clauses) > 1:
                    return clauses
        except Exception:
            pass

    # Regex fallback for compound sentence split
    compound_pattern = r",\s+(?:and|but|while|whereas)\s+(?=[A-Za-z0-9])"
    parts = re.split(compound_pattern, sentence, flags=re.IGNORECASE)
    if len(parts) > 1:
        valid_parts = []
        for p in parts:
            p_clean = p.strip(" .,;")
            # Ensure each part looks like a full clause with at least 2 words
            if len(p_clean.split()) >= 2:
                valid_parts.append(p_clean)
        if len(valid_parts) > 1:
            return valid_parts

    return [sentence]


def _extract_primary_entity(text: str) -> Optional[str]:
    """
    Extracts the main named entity (e.g. Person, Org, GPE) or subject from text.
    Used for coreference resolution across sequential sentences.
    """
    if nlp is not None:
        try:
            doc = nlp(text)
            # Prefer named entities: PERSON, ORG, GPE, PRODUCT
            for ent in doc.ents:
                if ent.label_ in {"PERSON", "ORG", "GPE", "PRODUCT", "WORK_OF_ART"}:
                    return ent.text
            # Fallback to noun subject
            for token in doc:
                if token.dep_ in {"nsubj", "nsubjpass"} and token.pos_ in {"PROPN", "NOUN"}:
                    # Extract the full noun chunk if possible
                    for chunk in doc.noun_chunks:
                        if token in chunk:
                            return chunk.text
                    return token.text
        except Exception:
            pass

    # Regex heuristic fallback: Look for capitalized names/nouns at the start
    match = re.match(r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", text)
    if match:
        candidate = match.group(1)
        if candidate.lower() not in {"the", "a", "an", "this", "that", "these", "those", "in", "on", "at"}:
            return candidate

    return None


def _decontextualize_sentence(sentence: str, last_entity: Optional[str]) -> str:
    """
    Replaces leading pronouns ('He', 'She', 'It', 'They') or demonstratives ('The former',
    'This person') with the resolved entity from prior context.
    Example:
        'He was born in 1961.' with last_entity='Barack Obama'
        -> 'Barack Obama was born in 1961.'
    """
    if not last_entity:
        return sentence

    # Match leading subject pronoun / demonstrative
    pattern = r"^(he|she|it|they|this\s+(?:person|individual|man|woman|company|organization))\b\s*"
    match = re.match(pattern, sentence, flags=re.IGNORECASE)
    if match:
        remainder = sentence[match.end():]
        return f"{last_entity} {remainder}".strip()

    return sentence


def extract_claims(answer_text: str) -> List[Claim]:
    """
    Splits a full AI answer into single checkable facts (claims).
    
    Fixed shared contract:
        Claim = {"claim_id": int, "text": str}
        extract_claims(answer_text) -> list[Claim]
        
    Pipeline:
    1. Sentence segmentation (spaCy or robust rule-based).
    2. Compound sentence splitting into atomic one-fact clauses.
    3. Non-claim filtering (removes greetings, opinions, questions, recommendations).
    4. Opinion prefix stripping (extracts factual core from 'I think X was Y').
    5. Decontextualization / pronoun resolution using preceding named entities.
    6. Packaging into schema {"claim_id": int, "text": str}.
    """
    if not answer_text or not isinstance(answer_text, str):
        return []

    # 1. Segment text into raw sentences
    if nlp is not None:
        try:
            doc = nlp(answer_text)
            raw_sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
        except Exception:
            raw_sentences = _split_into_sentences_regex(answer_text)
    else:
        raw_sentences = _split_into_sentences_regex(answer_text)

    claims: List[Claim] = []
    current_claim_id = 1
    last_known_entity: Optional[str] = None

    for raw_sentence in raw_sentences:
        # Strip conversational bullets or markdown markers (e.g. '* ', '1. ', '- ')
        cleaned = re.sub(r"^(?:[-*•]|\d+\.)\s+", "", raw_sentence).strip()
        if not cleaned:
            continue

        # Check for opinions with a factual inner statement: e.g. "I think Barack Obama was born in 1961"
        stripped_text, had_opinion = strip_opinion_prefix(cleaned)
        
        # 2. Split compound sentences into atomic units
        atomic_clauses = _split_compound_sentence(stripped_text)

        for clause in atomic_clauses:
            clause = clause.strip(" .,;")
            if not clause:
                continue

            # Ensure proper capitalization and sentence termination
            clause = clause[0].upper() + clause[1:]

            # 3. Apply non-claim filters
            if not is_valid_factual_claim(clause):
                continue

            # 4. Extract entity from clause to update context
            clause_entity = _extract_primary_entity(clause)
            if clause_entity and clause_entity.lower() not in PRONOUN_MAP:
                last_known_entity = clause_entity

            # 5. Decontextualize pronouns if present
            decontextualized = _decontextualize_sentence(clause, last_known_entity)
            if not decontextualized.endswith((".", "!", "?")):
                decontextualized += "."

            claims.append({
                "claim_id": current_claim_id,
                "text": decontextualized
            })
            current_claim_id += 1

    return claims


def analyze_claims(answer_text: str) -> Dict[str, Any]:
    """
    Analyzes input text, detects whether it contains factual claims or non-factual
    content (questions, emotions, self-referential dialogue, opinions, advice),
    and provides an explicit status message indicating what was found.
    
    Returns:
        Dict with:
            - 'claims': list[Claim] (all checkable factual claims extracted)
            - 'has_factual_claims': bool (True if at least one verifiable fact is present)
            - 'status_message': str (Human-readable explanation of what was detected)
            - 'breakdown': list[dict] (Sentence-by-sentence classification and feedback)
    """
    if not answer_text or not isinstance(answer_text, str) or not answer_text.strip():
        return {
            "claims": [],
            "has_factual_claims": False,
            "status_message": "Input is empty. Please provide text to analyze.",
            "breakdown": []
        }

    # Split into raw sentences
    if nlp is not None:
        try:
            doc = nlp(answer_text)
            raw_sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
        except Exception:
            raw_sentences = _split_into_sentences_regex(answer_text)
    else:
        raw_sentences = _split_into_sentences_regex(answer_text)

    breakdown = []
    detected_categories = set()

    for s in raw_sentences:
        cleaned = re.sub(r"^(?:[-*•]|\d+\.)\s+", "", s).strip()
        if not cleaned:
            continue
        classification = classify_statement(cleaned)
        breakdown.append(classification)
        detected_categories.add(classification["category"])

    # Extract actual claims
    claims = extract_claims(answer_text)
    has_factual = len(claims) > 0

    # Build human-readable diagnostic message
    if not has_factual:
        invalid_items = [item for item in breakdown if item["category"] in {"INVALID", "EMPTY"}]
        if invalid_items and len(invalid_items) == len(breakdown):
            msg = invalid_items[0]["message"]
        else:
            reasons = []
            if "INVALID" in detected_categories or "EMPTY" in detected_categories:
                reasons.append("invalid text (single words or random characters)")
            if "QUESTION" in detected_categories or "SELF_QUESTION" in detected_categories:
                reasons.append("questions")
            if "EMOTION" in detected_categories:
                reasons.append("personal emotions/feelings")
            if "SELF_REFERENTIAL" in detected_categories or "SELF_QUESTION" in detected_categories:
                reasons.append("personal/self-referential dialogue")
            if "OPINION" in detected_categories:
                reasons.append("subjective opinions")
            if "RECOMMENDATION" in detected_categories:
                reasons.append("advice/recommendations")
            if "GREETING_FILLER" in detected_categories:
                reasons.append("conversational greetings/fillers")

            if reasons:
                reason_str = ", ".join(reasons)
                msg = f"This is not a factual claim or checkable answer. The input contains {reason_str} rather than verifiable factual claims."
            else:
                msg = "This is not a factual claim or checkable answer. No verifiable factual claims were detected."
    else:
        non_factual_count = sum(1 for item in breakdown if not item["is_factual_claim"])
        if non_factual_count > 0:
            msg = f"Verified {len(claims)} factual claim(s). {non_factual_count} non-factual statement(s) (questions/emotions/opinions) were detected and excluded."
        else:
            msg = f"Successfully extracted {len(claims)} verifiable factual claim(s)."

    return {
        "claims": claims,
        "total_claims": len(claims),
        "has_factual_claims": has_factual,
        "status_message": msg,
        "breakdown": breakdown
    }
