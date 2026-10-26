"""
AI Input Module: Obtains the answer text to be tested from an AI model API
(e.g., OpenAI, Gemini, Anthropic) or a local Ollama instance.
Part of the Claim Extractor module owned by Pratham.
"""

import os
import json
import logging
from typing import Optional, Dict, Any

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)


def query_ollama(
    prompt: str,
    model: str = "llama3",
    base_url: str = "http://localhost:11434",
    timeout: int = 60
) -> str:
    """
    Query a local Ollama model to generate an answer text.
    
    Args:
        prompt: The user prompt or question to ask the model.
        model: Ollama model tag (default: 'llama3').
        base_url: Ollama API base URL.
        timeout: HTTP request timeout in seconds.
        
    Returns:
        The generated text response.
    """
    if requests is None:
        raise ImportError("The 'requests' package is required to call Ollama. Install via pip install requests.")

    url = f"{base_url.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to query local Ollama: {e}")
        raise RuntimeError(f"Ollama query failed: {e}") from e


def query_gemini(
    prompt: str,
    api_key: Optional[str] = None,
    model: str = "gemini-1.5-flash",
    timeout: int = 30
) -> str:
    """
    Query Google's Gemini API directly via REST.
    """
    if requests is None:
        raise ImportError("The 'requests' package is required to call Gemini API.")

    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY not found in environment or arguments.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()
    result = response.json()
    try:
        return result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected response format from Gemini: {result}") from e


def query_openai(
    prompt: str,
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini",
    timeout: int = 30
) -> str:
    """
    Query OpenAI-compatible chat completion API via standard REST.
    """
    if requests is None:
        raise ImportError("The 'requests' package is required to call OpenAI API.")

    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY not found in environment or arguments.")

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }

    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()
    result = response.json()
    try:
        return result["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected response format from OpenAI: {result}") from e


def get_ai_answer(
    prompt: str,
    provider: str = "ollama",
    **kwargs: Any
) -> str:
    """
    Universal dispatcher to fetch an AI-generated answer.
    
    Args:
        prompt: The query/prompt to test.
        provider: 'ollama', 'gemini', or 'openai'.
        **kwargs: Provider-specific configuration (model, api_key, etc.).
        
    Returns:
        Generated answer text ready to be passed to extract_claims().
    """
    provider = provider.lower()
    if provider == "ollama":
        return query_ollama(prompt, **kwargs)
    elif provider in {"gemini", "google"}:
        return query_gemini(prompt, **kwargs)
    elif provider in {"openai", "chatgpt"}:
        return query_openai(prompt, **kwargs)
    else:
        raise ValueError(f"Unsupported AI provider '{provider}'. Choose 'ollama', 'gemini', or 'openai'.")
