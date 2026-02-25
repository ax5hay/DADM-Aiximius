"""LLM client: OpenAI-compatible API or stub when no key is set."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional

import requests

# Stub response when USE_STUB_LLM=true or no API key. Use "stub" citation so guardrail passes when context empty.
STUB_RESPONSE = {
    "explanation_steps": [
        {"step_number": 1, "claim": "Subgraph context was loaded for the requested node.", "citations": ["stub"]},
        {"step_number": 2, "claim": "Risk and device nodes in the context are used for the explanation.", "citations": ["stub"]},
    ],
    "summary": "Stub explanation: no LLM configured. Enable OPENAI_API_KEY or set USE_STUB_LLM=false with another provider.",
    "confidence": 0.0,
    "confidence_justification": "Stub response; no real inference performed.",
}


def call_llm(system: str, user: str) -> tuple[Optional[Dict[str, Any]], str, int]:
    """
    Call LLM (OpenAI-compatible). Returns (parsed_json, response_type, latency_ms).
    response_type: "explanation" | "refused" | "error" | "invalid_output"
    """
    if os.environ.get("USE_STUB_LLM", "").lower() in ("1", "true", "yes"):
        return (STUB_RESPONSE, "explanation", 0)

    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")

    if not api_key:
        return (STUB_RESPONSE, "explanation", 0)

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 2048,
    }

    start = time.perf_counter()
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=60)
        latency_ms = int((time.perf_counter() - start) * 1000)
        if r.status_code == 200:
            data = r.json()
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            if not content:
                return (None, "error", latency_ms)
            # Try to parse JSON from content (strip markdown code blocks if present)
            raw = content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            try:
                parsed = json.loads(raw)
                return (parsed, "explanation", latency_ms)
            except json.JSONDecodeError:
                return (None, "invalid_output", latency_ms)
        if r.status_code in (401, 403):
            return (None, "refused", int((time.perf_counter() - start) * 1000))
        return (None, "error", int((time.perf_counter() - start) * 1000))
    except Exception:
        return (None, "error", int((time.perf_counter() - start) * 1000))
