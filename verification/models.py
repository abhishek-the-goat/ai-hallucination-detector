"""
verification/models.py
----------------------
ONNX Runtime inference for NLI and sentence embeddings.
Replaces PyTorch/Transformers to fit within Render's 512 MB memory limit.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

REPO_ROOT = Path(__file__).resolve().parent.parent
NLI_DIR = REPO_ROOT / "models" / "nli"
EMBED_DIR = REPO_ROOT / "models" / "embeddings"

# Lazy singleton model sessions and tokenizers
_nli_session: Optional[ort.InferenceSession] = None
_nli_tokenizer: Optional[Tokenizer] = None
_nli_id2label: Optional[dict[int, str]] = None
_nli_input_names: Optional[list[str]] = None

_embed_session: Optional[ort.InferenceSession] = None
_embed_tokenizer: Optional[Tokenizer] = None
_embed_input_names: Optional[list[str]] = None

# In-process cache to avoid recomputing embeddings for the same text
_embedding_cache: dict[str, np.ndarray] = {}


def _ensure_nli_loaded():
    global _nli_session, _nli_tokenizer, _nli_id2label, _nli_input_names
    if _nli_session is None or _nli_tokenizer is None or _nli_id2label is None:
        model_path = NLI_DIR / "model_quantized.onnx"
        tok_path = NLI_DIR / "tokenizer.json"
        cfg_path = NLI_DIR / "config.json"

        if not model_path.exists():
            # Trigger download if missing
            from scripts.download_models import main as download_all
            download_all()

        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        _nli_id2label = {int(k): v.lower() for k, v in cfg["id2label"].items()}

        _nli_tokenizer = Tokenizer.from_file(str(tok_path))
        _nli_session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        _nli_input_names = [inp.name for inp in _nli_session.get_inputs()]


def _ensure_embed_loaded():
    global _embed_session, _embed_tokenizer, _embed_input_names
    if _embed_session is None or _embed_tokenizer is None:
        model_path = EMBED_DIR / "model_quantized.onnx"
        tok_path = EMBED_DIR / "tokenizer.json"

        if not model_path.exists():
            from scripts.download_models import main as download_all
            download_all()

        _embed_tokenizer = Tokenizer.from_file(str(tok_path))
        _embed_session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        _embed_input_names = [inp.name for inp in _embed_session.get_inputs()]


def _load_models():
    """Load both ONNX sessions and tokenizers once and reuse them."""
    print("[verification.models] Loading ONNX models (nli-deberta-v3-small and all-MiniLM-L6-v2)...")
    _ensure_nli_loaded()
    _ensure_embed_loaded()
    print("[verification.models] ONNX models are ready.")


def get_nli_scores(premise: str, hypothesis: str) -> dict[str, float]:
    """
    Computes NLI classification scores for the given premise and hypothesis pair.
    Returns: {"entailment": float, "contradiction": float, "neutral": float}
    """
    _ensure_nli_loaded()
    encoding = _nli_tokenizer.encode(premise, hypothesis)

    feed = {
        "input_ids": np.array([encoding.ids], dtype=np.int64),
        "attention_mask": np.array([encoding.attention_mask], dtype=np.int64),
    }
    if _nli_input_names and "token_type_ids" in _nli_input_names:
        feed["token_type_ids"] = np.array([encoding.type_ids], dtype=np.int64)

    outputs = _nli_session.run(None, feed)
    logits = outputs[0][0]

    # Softmax
    exp = np.exp(logits - np.max(logits))
    probs = exp / np.sum(exp)

    scores = {"entailment": 0.0, "contradiction": 0.0, "neutral": 0.0}
    for idx, prob in enumerate(probs):
        label = _nli_id2label.get(idx, "")
        if label in scores:
            scores[label] = float(max(0.0, min(1.0, prob)))
    return scores


def get_embeddings(texts: list[str]) -> np.ndarray:
    """
    Returns float32 np.ndarray of shape (len(texts), 384) with L2-normalised embeddings.
    Uses in-process cache to avoid recomputing seen texts.
    """
    if not texts:
        return np.empty((0, 384), dtype=np.float32)

    # Check which texts need computation
    missing_indices = []
    missing_texts = []
    results = [None] * len(texts)

    for i, t in enumerate(texts):
        if t in _embedding_cache:
            results[i] = _embedding_cache[t]
        else:
            missing_indices.append(i)
            missing_texts.append(t)

    if missing_texts:
        _ensure_embed_loaded()
        encodings = [_embed_tokenizer.encode(t) for t in missing_texts]
        max_len = max(len(e.ids) for e in encodings)

        input_ids = []
        attention_mask = []
        token_type_ids = []
        for e in encodings:
            pad_len = max_len - len(e.ids)
            input_ids.append(e.ids + [0] * pad_len)
            attention_mask.append(e.attention_mask + [0] * pad_len)
            token_type_ids.append(e.type_ids + [0] * pad_len)

        feed = {
            "input_ids": np.array(input_ids, dtype=np.int64),
            "attention_mask": np.array(attention_mask, dtype=np.int64),
        }
        if _embed_input_names and "token_type_ids" in _embed_input_names:
            feed["token_type_ids"] = np.array(token_type_ids, dtype=np.int64)

        outputs = _embed_session.run(None, feed)
        token_embeddings = outputs[0]  # shape: (batch_size, seq_len, 384)
        mask = feed["attention_mask"][:, :, np.newaxis]  # (batch_size, seq_len, 1)

        # Mean pooling
        sum_embeddings = np.sum(token_embeddings * mask, axis=1)
        sum_mask = np.clip(np.sum(mask, axis=1), a_min=1e-9, a_max=None)
        mean_pooled = sum_embeddings / sum_mask

        # L2 normalize
        norm = np.linalg.norm(mean_pooled, axis=1, keepdims=True)
        norm = np.clip(norm, a_min=1e-12, a_max=None)
        normalized = (mean_pooled / norm).astype(np.float32)

        for idx, orig_idx in enumerate(missing_indices):
            vec = normalized[idx]
            _embedding_cache[missing_texts[idx]] = vec
            results[orig_idx] = vec

    return np.array(results, dtype=np.float32)


def get_embedding(text: str) -> np.ndarray:
    """Returns the 384-dim L2-normalised embedding vector for the input text."""
    return get_embeddings([text])[0]


def cosine_similarity(vec1, vec2) -> float:
    """Computes cosine similarity between two vectors, returning a float between 0.0 and 1.0."""
    v1 = np.asarray(vec1, dtype=float).ravel()
    v2 = np.asarray(vec2, dtype=float).ravel()
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    sim = float(np.dot(v1, v2) / (norm1 * norm2))
    return float(max(0.0, min(1.0, sim)))
