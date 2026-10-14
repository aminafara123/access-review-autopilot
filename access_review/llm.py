"""Thin, optional LLM wrapper: OpenAI-compatible chat endpoint, local ollama by default.

stdlib only. Returns None on any failure so callers fall back to templates and
tests never touch the network.
"""
from __future__ import annotations

import json
import os
import urllib.request

DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_MODEL = "qwen3:30b-a3b-instruct-2507-q4_K_M"


def chat(prompt: str, system: str = None, timeout: int = 30):
    """Return the model's text, or None if the LLM is unreachable/misconfigured."""
    base = os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = os.environ.get("LLM_MODEL", DEFAULT_MODEL)
    key = os.environ.get("LLM_API_KEY", "ollama")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({
        "model": model, "messages": messages, "temperature": 0.2, "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base}/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None  # offline / no model / bad response -> caller uses template
