import torch
import numpy as np

# Fix for PyTorch 2.6.0 CPU bug on Windows where torch.accelerator.current_accelerator()
# throws a RuntimeError when no accelerator is present.
if hasattr(torch, "accelerator"):
    try:
        torch.accelerator.current_accelerator()
    except RuntimeError:
        torch.accelerator.current_accelerator = lambda: None

from transformers import pipeline
from sentence_transformers import SentenceTransformer

# Lazy singleton model instances
_nli_pipeline = None
_embedding_model = None


def _load_models():
    """Load both DeBERTa NLI and MiniLM embedding models once and reuse them."""
    global _nli_pipeline, _embedding_model
    if _nli_pipeline is None or _embedding_model is None:
        print("[verification.models] Loading models (DeBERTa-v3-base-mnli-fever-anli and all-MiniLM-L6-v2)...")
        if _nli_pipeline is None:
            _nli_pipeline = pipeline(
                "text-classification",
                model="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
                device="cpu",
                top_k=None,
            )
        if _embedding_model is None:
            _embedding_model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
        print("[verification.models] Models are ready.")


def get_nli_scores(premise: str, hypothesis: str) -> dict:
    """
    Computes NLI classification scores for the given premise and hypothesis.
    Returns: {"entailment": float, "contradiction": float, "neutral": float}
    """
    _load_models()
    outputs = _nli_pipeline({"text": premise, "text_pair": hypothesis})
    if outputs and isinstance(outputs[0], list):
        outputs = outputs[0]

    scores = {"entailment": 0.0, "contradiction": 0.0, "neutral": 0.0}
    for item in outputs:
        label = item["label"].lower()
        if label in scores:
            scores[label] = float(item["score"])
    return scores


def get_embedding(text: str) -> np.ndarray:
    """Returns the embedding vector for the input text."""
    _load_models()
    return _embedding_model.encode(text)


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
