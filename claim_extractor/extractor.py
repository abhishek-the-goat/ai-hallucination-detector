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
    strip_opinion_prefix
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
            # Ensure each part looks like a full clause with at least 3 words
            if len(p_clean.split()) >= 3:
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

    # Leading pronoun patterns
    pronoun_patterns = [
        (r"^(?:he|she)\s+(?:was|is|became|moved|won|wrote|born|died|studied|graduated)\b", r"\1"),
        (r"^(?:he|she)\b", ""),
        (r"^(?:it)\b", ""),
        (r"^(?:they)\b", ""),
        (r"^(?:this\s+(?:person|individual|man|woman|company|organization))\b", ""),
    ]

    for pattern, _ in pronoun_patterns:
        match = re.search(pattern, sentence, flags=re.IGNORECASE)
        if match:
            # Replace the pronoun with the actual entity
            replaced = last_entity + sentence[match.end():]
            return replaced.strip()

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
