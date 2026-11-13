"""
scripts/download_models.py
--------------------------
Downloads the ONNX model files and tokenizers from Hugging Face Hub (public, no token)
into the local models/ directory:
    - models/nli/ (Xenova/nli-deberta-v3-small ONNX q8)
    - models/embeddings/ (Xenova/all-MiniLM-L6-v2 ONNX q8)

This script runs at Render build time and can also be run locally.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from huggingface_hub import hf_hub_download

REPO_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = REPO_ROOT / "models"
NLI_DIR = MODELS_DIR / "nli"
EMBED_DIR = MODELS_DIR / "embeddings"


def download_file(repo_id: str, filename: str, target_dir: Path, target_filename: str | None = None) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    dest_name = target_filename or Path(filename).name
    dest_path = target_dir / dest_name

    cached_path = hf_hub_download(repo_id=repo_id, filename=filename)
    if not dest_path.exists() or dest_path.stat().st_size != Path(cached_path).stat().st_size:
        shutil.copy2(cached_path, dest_path)

    size_mb = dest_path.stat().st_size / (1024 * 1024)
    print(f"Downloaded: {dest_path.relative_to(REPO_ROOT)} ({size_mb:.2f} MB)")
    return dest_path


def main():
    print(f"Downloading models into {MODELS_DIR}...")
    
    # 1. NLI: Xenova/nli-deberta-v3-small (q8 ONNX)
    nli_repo = "Xenova/nli-deberta-v3-small"
    download_file(nli_repo, "onnx/model_quantized.onnx", NLI_DIR, "model_quantized.onnx")
    download_file(nli_repo, "tokenizer.json", NLI_DIR, "tokenizer.json")
    download_file(nli_repo, "config.json", NLI_DIR, "config.json")

    # 2. Embeddings: Xenova/all-MiniLM-L6-v2 (q8 ONNX)
    embed_repo = "Xenova/all-MiniLM-L6-v2"
    download_file(embed_repo, "onnx/model_quantized.onnx", EMBED_DIR, "model_quantized.onnx")
    download_file(embed_repo, "tokenizer.json", EMBED_DIR, "tokenizer.json")
    download_file(embed_repo, "config.json", EMBED_DIR, "config.json")

    print("All models downloaded successfully.")


if __name__ == "__main__":
    main()

