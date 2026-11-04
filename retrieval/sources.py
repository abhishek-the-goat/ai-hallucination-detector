"""
retrieval/sources.py
--------------------
Multi-source live evidence fetchers for Wikipedia, Wikidata, and arXiv.

All fetchers share the same shape:
    fetch_<source>(claim_text: str, k: int = 5) -> list[dict]

Design principles:
- All sources are free and require NO API key.
- Shared requests.Session with standard User-Agent and a 5-second timeout.
- Robust error isolation: on ANY exception (timeout, connection error, bad response,
  empty results), each fetcher returns [] and logs/prints a warning so a dead
  source never crashes the pipeline.
- Every returned evidence dict satisfies the contract:
    {"text": str, "source_title": str, "source_url": str, "score": float, "source": str}
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
import requests

# ---------------------------------------------------------------------------
# Shared Session & Configuration
# ---------------------------------------------------------------------------

REQUEST_TIMEOUT: int = 5  # 5-second timeout on all network requests

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "AI-Hallucination-Detector/2.0 "
        "(https://github.com/abhishek-the-goat/ai-hallucination-detector; "
        "student research project)"
    )
})

# Common Wikidata Property ID to human-readable label mapping
WIKIDATA_PROPERTY_LABELS: Dict[str, str] = {
    "P31": "instance of",
    "P17": "country",
    "P36": "capital",
    "P1376": "capital of",
    "P1082": "population",
    "P569": "date of birth",
    "P570": "date of death",
    "P571": "inception",
    "P577": "publication date",
    "P106": "occupation",
    "P39": "position held",
    "P27": "country of citizenship",
    "P112": "founded by",
    "P170": "creator",
    "P50": "author",
    "P166": "award received",
    "P19": "place of birth",
    "P20": "place of death",
    "P69": "educated at",
    "P108": "employer",
    "P2044": "elevation above sea level",
    "P2046": "area",
    "P175": "performer",
    "P57": "director",
}


# ---------------------------------------------------------------------------
# Wikipedia Fetcher
# ---------------------------------------------------------------------------


def fetch_wikipedia(claim_text: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Fetch live Wikipedia evidence passages for claim_text using the existing
    live Wikipedia retrieval engine.

    Returns list of Evidence dicts with source='wikipedia', or [] on error.
    """
    if not claim_text or not claim_text.strip():
        return []

    try:
        from retrieval.live_search import retrieve_live_evidence
        raw_evidence = retrieve_live_evidence(claim_text, k=k)
        results: List[Dict[str, Any]] = []
        for item in raw_evidence:
            ev = dict(item)
            ev["source"] = "wikipedia"
            results.append(ev)
        return results
    except Exception as exc:
        print(f"[retrieval.sources] Warning: Wikipedia live search failed ({exc}). Continuing...")
        return []


# ---------------------------------------------------------------------------
# Wikidata Fetcher
# ---------------------------------------------------------------------------


def _extract_wikidata_search_candidates(text: str) -> List[str]:
    """Generate prioritized candidate entity names from claim text."""
    clean = text.strip().rstrip(".!?")
    candidates: List[str] = [clean]

    # Split before common verbs/copulas to isolate subject
    split_match = re.split(
        r"\b(?:is|was|are|were|has|had|won|born|created|launched|located|serves|served|produces|died)\b",
        clean,
        flags=re.IGNORECASE,
    )
    if split_match and split_match[0].strip():
        subj = split_match[0].strip()
        subj_clean = re.sub(r"^(?:the|a|an)\s+", "", subj, flags=re.IGNORECASE).strip()
        if subj_clean and subj_clean not in candidates:
            candidates.append(subj_clean)

    # Capitalized multi-word phrases (proper nouns)
    proper_nouns = re.findall(r"\b[A-Z][a-zA-Z0-9_]*(?:\s+[A-Z][a-zA-Z0-9_]*)*\b", clean)
    for pn in proper_nouns:
        pn_clean = re.sub(r"^(?:The|A|An)\s+", "", pn).strip()
        if pn_clean and len(pn_clean) > 1 and pn_clean not in candidates:
            candidates.append(pn_clean)

    return candidates


def _format_wikidata_value(datavalue: Any) -> Optional[str]:
    """Extract a displayable string from a Wikidata snak datavalue."""
    if not isinstance(datavalue, dict):
        return str(datavalue) if datavalue is not None else None

    val = datavalue.get("value")
    if isinstance(val, str):
        return val
    elif isinstance(val, (int, float)):
        return str(val)
    elif isinstance(val, dict):
        if "amount" in val:
            # Quantity, e.g. "+2145906"
            return str(val["amount"]).lstrip("+")
        elif "time" in val:
            # ISO timestamp, e.g. "+1961-08-04T00:00:00Z"
            time_str = str(val["time"]).lstrip("+")
            time_match = re.search(r"(\d{4}(?:-\d{2}-\d{2})?)", time_str)
            return time_match.group(1) if time_match else time_str
        elif "text" in val:
            # Monolingual text
            return str(val["text"])
        elif "label" in val:
            return str(val["label"])
        elif "id" in val:
            return str(val["id"])

    return None


def fetch_wikidata(claim_text: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Fetch structured entity facts from Wikidata using wbsearchentities and Special:EntityData.

    Returns list of Evidence dicts with source='wikidata', or [] on error/no entity.
    """
    if not claim_text or not claim_text.strip():
        return []

    try:
        search_terms = _extract_wikidata_search_candidates(claim_text)
        entity_id: Optional[str] = None
        entity_label: Optional[str] = None
        entity_desc: Optional[str] = None

        # 1. Search Wikidata for candidate entities via wbsearchentities
        search_url = "https://www.wikidata.org/w/api.php"
        for term in search_terms:
            params = {
                "action": "wbsearchentities",
                "search": term,
                "language": "en",
                "format": "json",
                "limit": 3,
            }
            resp = _SESSION.get(search_url, params=params, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("search", [])
                if results:
                    top_match = results[0]
                    entity_id = top_match.get("id")
                    entity_label = (
                        top_match.get("label")
                        or top_match.get("display", {}).get("label", {}).get("value")
                        or term
                    )
                    entity_desc = (
                        top_match.get("description")
                        or top_match.get("display", {}).get("description", {}).get("value")
                    )
                    break

        if not entity_id:
            return []

        # 2. Fetch entity data via Special:EntityData
        entity_url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
        data_resp = _SESSION.get(entity_url, timeout=REQUEST_TIMEOUT)
        if data_resp.status_code != 200:
            print(f"[retrieval.sources] Warning: Wikidata Special:EntityData returned status {data_resp.status_code}")
            return []

        entity_json = data_resp.json()
        entities = entity_json.get("entities", {})
        entity_data = entities.get(entity_id, {})

        label = (
            entity_data.get("labels", {}).get("en", {}).get("value")
            or entity_label
            or entity_id
        )
        description = (
            entity_data.get("descriptions", {}).get("en", {}).get("value")
            or entity_desc
        )

        evidence_items: List[Dict[str, Any]] = []

        # Include description sentence if available (e.g. "Paris - capital of France (Wikidata)")
        if description:
            desc_sentence = f"{label} - {description} (Wikidata)"
            evidence_items.append({
                "text": desc_sentence,
                "source_title": f"{label} - Wikidata",
                "source_url": f"https://www.wikidata.org/wiki/{entity_id}",
                "score": 1.0,
                "raw_similarity": 1.0,
                "cosine_similarity": 1.0,
                "source": "wikidata",
            })

        # Parse structured claims
        claims_dict = entity_data.get("claims", {})
        for prop_id, statements in claims_dict.items():
            if not isinstance(statements, list):
                # Handle simplified test mocks: {"property": "capital of", "value": "France"}
                if isinstance(statements, dict) and "value" in statements:
                    prop_name = statements.get("property", prop_id)
                    val_str = str(statements["value"])
                    sentence = f"{label} - {prop_name}: {val_str} (Wikidata)"
                    evidence_items.append({
                        "text": sentence,
                        "source_title": f"{label} - Wikidata",
                        "source_url": f"https://www.wikidata.org/wiki/{entity_id}",
                        "score": 1.0,
                        "raw_similarity": 1.0,
                        "cosine_similarity": 1.0,
                        "source": "wikidata",
                    })
                continue

            prop_name = WIKIDATA_PROPERTY_LABELS.get(prop_id, prop_id)
            for stmt in statements:
                if not isinstance(stmt, dict):
                    continue

                # Support both standard snak datavalue and simplified mock formats
                val_str: Optional[str] = None
                if "mainsnak" in stmt:
                    snak = stmt["mainsnak"]
                    p_id = snak.get("property", prop_id)
                    prop_name = WIKIDATA_PROPERTY_LABELS.get(p_id, p_id)
                    val_str = _format_wikidata_value(snak.get("datavalue"))
                elif "value" in stmt:
                    val_str = str(stmt["value"])
                    prop_name = stmt.get("property", prop_name)

                if val_str:
                    sentence = f"{label} - {prop_name}: {val_str} (Wikidata)"
                    evidence_items.append({
                        "text": sentence,
                        "source_title": f"{label} - Wikidata",
                        "source_url": f"https://www.wikidata.org/wiki/{entity_id}",
                        "score": 1.0,
                        "raw_similarity": 1.0,
                        "cosine_similarity": 1.0,
                        "source": "wikidata",
                    })

                if len(evidence_items) >= k:
                    break

            if len(evidence_items) >= k:
                break

        return evidence_items[:k]

    except Exception as exc:
        print(f"[retrieval.sources] Warning: Wikidata fetch failed ({exc}). Continuing...")
        return []


# ---------------------------------------------------------------------------
# arXiv Fetcher
# ---------------------------------------------------------------------------


def fetch_arxiv(claim_text: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Fetch scientific evidence from the arXiv API (export.arxiv.org/api/query, Atom feed).

    Returns list of Evidence dicts with source='arxiv', or [] on error/no papers.
    """
    if not claim_text or not claim_text.strip():
        return []

    try:
        # Sanitize query for arXiv search
        clean_q = re.sub(r"[^\w\s-]", " ", claim_text.strip())
        clean_q = " ".join(clean_q.split()[:12])  # Keep first 12 keywords for focus

        arxiv_url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": f"all:{clean_q}",
            "start": 0,
            "max_results": max(int(k), 3),
        }

        resp = _SESSION.get(arxiv_url, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            print(f"[retrieval.sources] Warning: arXiv query returned status {resp.status_code}")
            return []

        root = ET.fromstring(resp.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        entries = root.findall("atom:entry", ns)
        if not entries:
            entries = root.findall("entry")

        if not entries:
            return []

        evidence_items: List[Dict[str, Any]] = []
        for entry in entries:
            title_node = entry.find("atom:title", ns) if "atom" in ns else None
            if title_node is None:
                title_node = entry.find("title")

            summary_node = entry.find("atom:summary", ns) if "atom" in ns else None
            if summary_node is None:
                summary_node = entry.find("summary")

            id_node = entry.find("atom:id", ns) if "atom" in ns else None
            if id_node is None:
                id_node = entry.find("id")

            title = (title_node.text or "").strip().replace("\n", " ") if title_node is not None else "Research Paper"
            title = re.sub(r"\s+", " ", title)

            summary = (summary_node.text or "").strip().replace("\n", " ") if summary_node is not None else ""
            summary = re.sub(r"\s+", " ", summary)

            url = (id_node.text or "").strip() if id_node is not None else "https://arxiv.org"

            # Use title + summary first sentence as evidence
            first_sentence = ""
            if summary:
                sents = re.split(r"(?<=[.!?])\s+", summary)
                first_sentence = sents[0].strip() if sents else summary

            ev_text = f"{title}. {first_sentence}" if first_sentence else title

            evidence_items.append({
                "text": ev_text,
                "source_title": f"{title} — arXiv",
                "source_url": url,
                "score": 1.0,
                "raw_similarity": 1.0,
                "cosine_similarity": 1.0,
                "source": "arxiv",
            })

            if len(evidence_items) >= k:
                break

        return evidence_items[:k]

    except Exception as exc:
        print(f"[retrieval.sources] Warning: arXiv fetch failed ({exc}). Continuing...")
        return []
