"""
retrieval/corpus.py
-------------------
Manages the trusted document corpus for the AI Hallucination Detector.

Responsibilities
----------------
- Define the Document data structure.
- Split long articles into overlapping ~200-300 word passages.
- Persist / load the corpus as a local JSON file (offline-safe).
- Optionally expand the corpus by fetching Wikipedia articles via the
  MediaWiki REST API (network calls only happen when explicitly requested).

Nothing in this module triggers a network request or model load on import.
"""

from __future__ import annotations

import json
import os
import re
import textwrap
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Default location for the bundled corpus JSON file.
_MODULE_DIR = Path(__file__).parent
CORPUS_PATH: Path = _MODULE_DIR / "data" / "corpus.json"

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Document:
    """A single retrievable passage from a trusted source."""

    id: str           # Unique passage identifier, e.g. "wiki:Eiffel_Tower:0"
    text: str         # Passage text (~200-300 words)
    source_title: str # Human-readable article title, e.g. "Eiffel Tower - Wikipedia"
    source_url: str   # Canonical URL for the article


# ---------------------------------------------------------------------------
# Passage splitting
# ---------------------------------------------------------------------------

_TARGET_WORDS = 250   # Aim for this many words per passage
_MIN_WORDS    = 40    # Passages shorter than this are merged into the previous one


def _split_into_passages(
    text: str,
    source_title: str,
    source_url: str,
    doc_key: str,
    target_words: int = _TARGET_WORDS,
    min_words: int = _MIN_WORDS,
) -> list[Document]:
    """
    Split *text* into passages of approximately *target_words* words.

    Strategy
    --------
    1. Split on sentence boundaries (`. `, `! `, `? `, newlines).
    2. Greedily accumulate sentences until the passage reaches *target_words*.
    3. If the final passage is shorter than *min_words*, append it to the
       previous passage rather than leaving a tiny orphan.
    4. Each passage becomes one Document.

    Returns an empty list if *text* is blank.
    """
    if not text or not text.strip():
        return []

    # Tokenise into sentences. Keep the delimiter attached.
    sentences: list[str] = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return []

    passages: list[str] = []
    current_words: list[str] = []

    for sentence in sentences:
        words = sentence.split()
        current_words.extend(words)

        if len(current_words) >= target_words:
            passages.append(" ".join(current_words))
            current_words = []

    # Flush remaining words
    if current_words:
        leftover = " ".join(current_words)
        if passages and len(current_words) < min_words:
            # Merge tiny tail into the previous passage
            passages[-1] = passages[-1] + " " + leftover
        else:
            passages.append(leftover)

    # Handle the degenerate case where the whole article is shorter than min_words
    if not passages:
        passages = [" ".join(sentences)]

    documents: list[Document] = []
    for idx, passage_text in enumerate(passages):
        documents.append(Document(
            id=f"{doc_key}:{idx}",
            text=passage_text.strip(),
            source_title=source_title,
            source_url=source_url,
        ))

    return documents


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_corpus(documents: list[Document], path: Path = CORPUS_PATH) -> None:
    """
    Serialise *documents* to a JSON file at *path*.

    The parent directory is created if it does not exist.
    Raises ``IOError`` if the file cannot be written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump([asdict(d) for d in documents], fh, indent=2, ensure_ascii=False)
    print(f"[corpus] Saved {len(documents)} passages → {path}")


def load_corpus(path: Path = CORPUS_PATH) -> list[Document]:
    """
    Load the corpus from *path* and return a list of Documents.

    Returns an empty list (and prints a warning) if the file:
    - does not exist
    - is empty or contains invalid JSON
    - contains records missing required fields
    """
    path = Path(path)

    if not path.exists():
        print(f"[corpus] Warning: corpus file not found at {path}. "
              "Run build_corpus() to create it.")
        return []

    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        print(f"[corpus] Warning: cannot read corpus file ({exc}).")
        return []

    if not raw:
        print(f"[corpus] Warning: corpus file is empty at {path}.")
        return []

    try:
        records = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[corpus] Warning: malformed JSON in corpus file ({exc}).")
        return []

    if not isinstance(records, list):
        print("[corpus] Warning: corpus JSON is not a list.")
        return []

    documents: list[Document] = []
    required = {"id", "text", "source_title", "source_url"}

    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            print(f"[corpus] Warning: record {i} is not a dict — skipped.")
            continue
        missing = required - rec.keys()
        if missing:
            print(f"[corpus] Warning: record {i} missing fields {missing} — skipped.")
            continue
        if not rec.get("text", "").strip():
            # Skip passages with empty text
            continue
        documents.append(Document(
            id=str(rec["id"]),
            text=rec["text"],
            source_title=rec["source_title"],
            source_url=rec["source_url"],
        ))

    print(f"[corpus] Loaded {len(documents)} passages from {path}")
    return documents


# ---------------------------------------------------------------------------
# Wikipedia fetcher (network — only called explicitly)
# ---------------------------------------------------------------------------

_WIKI_API = "https://en.wikipedia.org/w/api.php"


def _fetch_wikipedia_article(title: str) -> Optional[tuple[str, str, str]]:
    """
    Fetch the plain-text extract for a Wikipedia article.

    Returns ``(plain_text, display_title, canonical_url)`` on success,
    or ``None`` on any failure (network error, missing article, etc.).

    Requires `requests` to be installed.
    """
    try:
        import requests  # local import — no network on module load
    except ImportError:
        print("[corpus] Warning: 'requests' is not installed — cannot fetch Wikipedia.")
        return None

    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "extracts|info",
        "explaintext": True,
        "exsectionformat": "plain",
        "inprop": "url",
        "redirects": True,
    }

    try:
        resp = requests.get(_WIKI_API, params=params, timeout=15,
                            headers={"User-Agent": "ai-hallucination-detector/1.0"})
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        print(f"[corpus] Warning: Wikipedia fetch failed for '{title}': {exc}")
        return None

    pages = data.get("query", {}).get("pages", {})
    if not pages:
        print(f"[corpus] Warning: no pages returned for '{title}'.")
        return None

    page = next(iter(pages.values()))
    if page.get("missing") is not None or "extract" not in page:
        print(f"[corpus] Warning: article '{title}' not found on Wikipedia.")
        return None

    extract: str = page["extract"]
    display_title: str = page.get("title", title)
    canonical_url: str = page.get("fullurl", f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}")

    # Strip section headers like "== History ==" and clean blank lines
    extract = re.sub(r"={2,}[^=]+=={2,}", "", extract)
    extract = re.sub(r"\n{3,}", "\n\n", extract).strip()

    return extract, display_title, canonical_url


# Default articles used to seed the corpus
DEFAULT_ARTICLES: list[str] = [
    "Eiffel Tower",
    "Albert Einstein",
    "World War II",
    "Python (programming language)",
    "Photosynthesis",
    "Moon",
    "Marie Curie",
    "DNA",
    "Climate change",
    "United States",
]


def build_corpus(
    articles: Optional[list[str]] = None,
    path: Path = CORPUS_PATH,
    append: bool = False,
) -> list[Document]:
    """
    Fetch Wikipedia articles and build (or extend) the local corpus file.

    Parameters
    ----------
    articles : list of Wikipedia article titles to fetch.
               Defaults to DEFAULT_ARTICLES.
    path     : where to save the resulting corpus JSON.
    append   : if True, merge new passages with any existing corpus instead of
               replacing it.

    Returns the full list of Documents written to *path*.

    Network calls are only made from this function — importing the module is safe.
    """
    if articles is None:
        articles = DEFAULT_ARTICLES

    existing: list[Document] = load_corpus(path) if append else []
    existing_ids = {d.id for d in existing}

    new_docs: list[Document] = list(existing)

    for article_title in articles:
        print(f"[corpus] Fetching '{article_title}' from Wikipedia…")
        result = _fetch_wikipedia_article(article_title)
        if result is None:
            continue

        text, display_title, url = result
        doc_key = f"wiki:{article_title.replace(' ', '_')}"
        source_title = f"{display_title} - Wikipedia"

        passages = _split_into_passages(
            text=text,
            source_title=source_title,
            source_url=url,
            doc_key=doc_key,
        )

        added = 0
        for doc in passages:
            if doc.id not in existing_ids:
                new_docs.append(doc)
                existing_ids.add(doc.id)
                added += 1

        print(f"[corpus] '{article_title}': {len(passages)} passages ({added} new).")

    save_corpus(new_docs, path)
    return new_docs
