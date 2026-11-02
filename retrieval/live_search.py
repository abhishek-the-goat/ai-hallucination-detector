"""
retrieval/live_search.py
------------------------
Live Wikipedia retrieval engine.

Responsibilities:
1. Search Wikipedia via MediaWiki API for claim text -> top 3 article titles.
2. Fetch plain text of each article via prop=extracts&explaintext=1.
3. Cache fetched articles under retrieval/data/wiki_cache/ keyed by title.
4. Split each article into passages of 3-5 sentences.
5. Embed passages with all-MiniLM-L6-v2 and rank by raw cosine similarity.
6. Return top-k passages as Evidence dicts with score = raw cosine similarity.
"""

from __future__ import annotations

import os
import re
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

import numpy as np

# PyTorch accelerator bug fix for Windows CPU environments
try:
    import torch
    if hasattr(torch, "accelerator"):
        try:
            torch.accelerator.current_accelerator()
        except RuntimeError:
            torch.accelerator.current_accelerator = lambda: None
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Constants & Configuration
# ---------------------------------------------------------------------------

WIKI_API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "AI-Hallucination-Detector/1.0 (https://github.com/abhishek-the-goat/ai-hallucination-detector; student research project)"
REQUEST_TIMEOUT = 10  # 10-second timeout on every request

_MODULE_DIR = Path(__file__).resolve().parent
WIKI_CACHE_DIR = _MODULE_DIR / "data" / "wiki_cache"

# Lazy-loaded singleton for SentenceTransformer
_embedding_model = None


def _get_embedding_model():
    """Lazy load all-MiniLM-L6-v2 once, preferring local cache first."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        try:
            _embedding_model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu", local_files_only=True)
        except Exception:
            _embedding_model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    return _embedding_model


def _safe_filename(title: str) -> str:
    """Return a safe filesystem name for the Wikipedia article title."""
    cleaned = re.sub(r'[\\/*?:"<>|]', "_", title).strip()
    return f"{cleaned}.json"


# ---------------------------------------------------------------------------
# Cache Management
# ---------------------------------------------------------------------------

def _load_from_cache(title: str) -> Optional[dict]:
    """Retrieve an article from the local wiki cache if present."""
    cache_path = WIKI_CACHE_DIR / _safe_filename(title)
    if not cache_path.is_file():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "text" in data and data["text"].strip():
            return data
    except Exception:
        pass
    return None


def _save_to_cache(title: str, text: str, url: str) -> None:
    """Persist an article to the local wiki cache."""
    try:
        WIKI_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = WIKI_CACHE_DIR / _safe_filename(title)
        cache_path.write_text(
            json.dumps({"title": title, "url": url, "text": text}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"[live_search] Cache write warning for '{title}': {exc}")


# ---------------------------------------------------------------------------
# Wikipedia Fetcher
# ---------------------------------------------------------------------------

def search_wikipedia_titles(query: str, limit: int = 3) -> List[str]:
    """
    Search Wikipedia via MediaWiki API and return the top article titles.
    Checks query cache / cached titles if offline or on network error.
    """
    norm_query = query.strip().lower()
    query_cache_file = WIKI_CACHE_DIR / "_queries.json"
    cached_queries = {}
    if query_cache_file.is_file():
        try:
            cached_queries = json.loads(query_cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    if norm_query in cached_queries:
        return cached_queries[norm_query][:limit]

    import requests

    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
    }
    headers = {"User-Agent": USER_AGENT}

    try:
        resp = requests.get(WIKI_API_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        search_items = data.get("query", {}).get("search", [])
        titles = [item["title"] for item in search_items if "title" in item]
        if titles:
            cached_queries[norm_query] = titles
            try:
                WIKI_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                query_cache_file.write_text(json.dumps(cached_queries, indent=2), encoding="utf-8")
            except Exception:
                pass
        return titles[:limit]
    except Exception:
        # Offline / network error fallback: check cached article files in wiki_cache/
        matched = []
        if WIKI_CACHE_DIR.is_dir():
            for f in WIKI_CACHE_DIR.glob("*.json"):
                if f.name.startswith("_"):
                    continue
                title_name = f.stem
                if title_name.lower() in norm_query or any(word in norm_query for word in title_name.lower().split() if len(word) > 3):
                    matched.append(title_name)
        return matched[:limit]


def fetch_article_text(title: str) -> Optional[tuple[str, str, str]]:
    """
    Fetch an article's plain text extract.
    Checks cache first; if missing, requests from Wikipedia API.
    Returns (clean_text, display_title, canonical_url) or None on failure.
    """
    # 1. Check cache first
    cached = _load_from_cache(title)
    if cached is not None:
        return cached["text"], cached.get("title", title), cached.get("url", f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}")

    # 2. Fetch from MediaWiki API
    import requests

    params = {
        "action": "query",
        "prop": "extracts|info",
        "explaintext": "1",
        "exsectionformat": "plain",
        "titles": title,
        "format": "json",
        "inprop": "url",
        "redirects": "1",
    }
    headers = {"User-Agent": USER_AGENT}

    resp = requests.get(WIKI_API_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return None

    page = next(iter(pages.values()))
    if page.get("missing") is not None or "extract" not in page:
        return None

    raw_extract = page["extract"]
    display_title = page.get("title", title)
    canonical_url = page.get("fullurl", f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}")

    # Clean headers and extra whitespace
    clean_text = re.sub(r"={2,}[^=]+=={2,}", "", raw_extract)
    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()

    if clean_text:
        _save_to_cache(display_title, clean_text, canonical_url)

    return clean_text, display_title, canonical_url


# ---------------------------------------------------------------------------
# Passage Splitting & Ranking
# ---------------------------------------------------------------------------

def split_into_passages(text: str, min_sents: int = 3, max_sents: int = 5) -> List[str]:
    """
    Split an article into passages of 3-5 sentences with overlapping stride.
    """
    if not text or not text.strip():
        return []

    # Split on sentence boundaries
    raw_sents = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in raw_sents if s.strip() and len(s.split()) >= 3]

    if not sentences:
        return [text.strip()] if text.strip() else []

    if len(sentences) <= max_sents:
        return [" ".join(sentences)]

    passages = []
    chunk_size = 4  # 3-5 sentence window
    stride = 3

    for i in range(0, len(sentences) - chunk_size + 1, stride):
        passages.append(" ".join(sentences[i : i + chunk_size]))

    # Append any remaining tail sentences
    if (len(sentences) - chunk_size) % stride != 0:
        tail = " ".join(sentences[-chunk_size:])
        if tail not in passages:
            passages.append(tail)

    return passages


def retrieve_live_evidence(claim_text: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Perform live Wikipedia search for claim_text, chunk articles into passages,
    embed and rank by raw cosine similarity, and return top-k Evidence dicts.

    Returns [] if no articles found or any error occurs (allowing caller fallback).
    """
    if not claim_text or not claim_text.strip():
        return []

    k = max(1, int(k))

    # 1. Search Wikipedia for top 3 article titles
    titles = search_wikipedia_titles(claim_text, limit=3)
    if not titles:
        return []

    # 2. Fetch extracts for each title
    articles = []
    for title in titles:
        res = fetch_article_text(title)
        if res is not None:
            text, display_title, url = res
            if text:
                articles.append((text, display_title, url))

    if not articles:
        return []

    # 3. Split each article into passages of 3-5 sentences
    candidate_passages = []
    for text, display_title, url in articles:
        passages = split_into_passages(text, min_sents=3, max_sents=5)
        for p in passages:
            candidate_passages.append({
                "text": p,
                "source_title": f"{display_title} - Wikipedia",
                "source_url": url,
            })

    if not candidate_passages:
        return []

    # 4. Embed passages and claim with all-MiniLM-L6-v2
    model = _get_embedding_model()
    q_emb = model.encode([claim_text], convert_to_numpy=True, normalize_embeddings=True)[0]
    p_texts = [p["text"] for p in candidate_passages]
    p_embs = model.encode(p_texts, batch_size=32, convert_to_numpy=True, normalize_embeddings=True)

    # 5. Compute raw cosine similarity via dot product (since normalized)
    raw_similarities = np.dot(p_embs, q_emb)

    # 6. Rank passages descending
    ranked_indices = np.argsort(-raw_similarities)

    evidence_list = []
    for idx in ranked_indices[:k]:
        sim = float(np.clip(raw_similarities[idx], 0.0, 1.0))
        cand = candidate_passages[idx]
        evidence_list.append({
            "text": cand["text"],
            "source_title": cand["source_title"],
            "source_url": cand["source_url"],
            "score": round(sim, 6),
            "raw_similarity": round(sim, 6),
            "cosine_similarity": round(sim, 6),
        })

    return evidence_list

