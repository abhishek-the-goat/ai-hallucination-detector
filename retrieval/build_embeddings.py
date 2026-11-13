"""
retrieval/build_embeddings.py
-----------------------------
Precomputes corpus embeddings using verification.models.get_embeddings (ONNX MiniLM).
Saves:
    - retrieval/data/corpus_embeddings.npy (float32 array)
    - retrieval/data/corpus_embeddings.json (manifest of doc ids in exact order)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from retrieval.corpus import load_corpus
from verification.models import get_embeddings

DATA_DIR = REPO_ROOT / "retrieval" / "data"
NPY_PATH = DATA_DIR / "corpus_embeddings.npy"
JSON_PATH = DATA_DIR / "corpus_embeddings.json"


def build_embeddings(batch_size: int = 64) -> tuple[np.ndarray, list[str]]:
    docs = load_corpus()
    if not docs:
        raise RuntimeError("Corpus is empty, cannot build embeddings.")

    print(f"[build_embeddings] Loaded {len(docs)} passages from corpus.")
    texts = [d.text for d in docs]
    doc_ids = [d.id for d in docs]

    all_vectors = []
    total = len(texts)
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch = texts[start:end]
        vecs = get_embeddings(batch)
        all_vectors.append(vecs)
        print(f"[build_embeddings] Processed {end}/{total} passages...")

    embeddings = np.vstack(all_vectors).astype(np.float32)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    np.save(str(NPY_PATH), embeddings)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(doc_ids, f, indent=2)

    print(f"[build_embeddings] Successfully saved embeddings:")
    print(f"  - Passages: {len(doc_ids)}")
    print(f"  - Vector shape: {embeddings.shape}")
    print(f"  - Saved to: {NPY_PATH.relative_to(REPO_ROOT)} and {JSON_PATH.relative_to(REPO_ROOT)}")

    return embeddings, doc_ids


if __name__ == "__main__":
    build_embeddings()

