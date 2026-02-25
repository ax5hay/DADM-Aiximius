#!/usr/bin/env python3
"""
Reasoning layer: POST /v1/reason — fetch subgraph, build prompt, call LLM, validate, guardrail, audit.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import requests
from flask import Flask, jsonify, request

from audit import write_audit_entry
from guardrails import collect_context_ids, validate_citations
from llm_client import call_llm
from prompts import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt

app = Flask(__name__)

GRAPH_API_URL = os.environ.get("GRAPH_API_URL", "http://localhost:5001")


def fetch_subgraph(node_id: str, hops: int = 2) -> dict:
    """GET subgraph from graph API."""
    url = f"{GRAPH_API_URL.rstrip('/')}/api/v1/subgraph"
    params = {"node_id": node_id, "hops": hops}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def validate_explanation_schema(data: dict) -> tuple[bool, str]:
    """Basic validation: required keys and types. Returns (ok, error_message)."""
    required = ["explanation_steps", "summary", "confidence", "confidence_justification"]
    for k in required:
        if k not in data:
            return (False, f"missing field: {k}")
    if not isinstance(data["explanation_steps"], list) or len(data["explanation_steps"]) < 1:
        return (False, "explanation_steps must be a non-empty array")
    for i, step in enumerate(data["explanation_steps"]):
        if not isinstance(step, dict):
            return (False, f"explanation_steps[{i}] must be an object")
        for f in ("step_number", "claim", "citations"):
            if f not in step:
                return (False, f"explanation_steps[{i}] missing '{f}'")
        if not isinstance(step["citations"], list):
            return (False, f"explanation_steps[{i}].citations must be an array")
        if len(step["citations"]) < 1:
            return (False, f"explanation_steps[{i}].citations must have at least one citation")
    c = data.get("confidence")
    if not isinstance(c, (int, float)) or c < 0 or c > 1:
        return (False, "confidence must be a number between 0 and 1")
    return (True, "")


@app.route("/v1/reason", methods=["POST"])
def reason():
    """POST { query, node_id [, hops ] } -> explanation with citations and audit log."""
    body = request.get_json() or {}
    query = body.get("query") or body.get("q")
    node_id = body.get("node_id") or body.get("node")
    hops = int(body.get("hops", 2))

    if not query or not node_id:
        return jsonify({"error": "missing query or node_id"}), 400

    request_id = str(uuid4())
    context_node_count = 0
    context_edge_count = 0
    context_ids_list = []
    subgraph = {}

    try:
        subgraph = fetch_subgraph(node_id, hops=hops)
        nodes = subgraph.get("nodes", [])
        edges = subgraph.get("edges", [])
        context_node_count = len(nodes)
        context_edge_count = len(edges)
        context_ids = collect_context_ids(subgraph)
        context_ids.add("stub")  # so stub LLM response passes citation guardrail
        context_ids_list = list(context_ids)
        structured_context = json.dumps(subgraph, indent=2)
    except Exception as e:
        write_audit_entry({
            "request_id": request_id,
            "prompt_version": PROMPT_VERSION,
            "query": query,
            "model": "n/a",
            "response_type": "error",
            "error_message": str(e),
        })
        return jsonify({"error": "failed to fetch subgraph", "detail": str(e)}), 502

    user_prompt = build_user_prompt(structured_context, query)
    parsed, response_type, latency_ms = call_llm(SYSTEM_PROMPT, user_prompt)

    audit = {
        "request_id": request_id,
        "prompt_version": PROMPT_VERSION,
        "query": query,
        "context_node_count": context_node_count,
        "context_edge_count": context_edge_count,
        "context_node_ids": context_ids_list[:100],
        "model": os.environ.get("LLM_MODEL", "stub"),
        "response_type": response_type,
        "latency_ms": latency_ms,
    }

    if response_type != "explanation" or parsed is None:
        audit["error_message"] = "LLM returned no valid explanation"
        write_audit_entry(audit)
        return jsonify({"error": "no explanation", "response_type": response_type}), 422

    ok, err = validate_explanation_schema(parsed)
    if not ok:
        audit["response_type"] = "invalid_output"
        audit["error_message"] = err
        write_audit_entry(audit)
        return jsonify({"error": "invalid output schema", "detail": err}), 422

    all_valid, invalid_cites = validate_citations(parsed["explanation_steps"], context_ids)
    audit["citation_count"] = sum(len(s.get("citations", [])) for s in parsed["explanation_steps"])
    audit["citation_ids"] = [
        c for s in parsed["explanation_steps"] for c in s.get("citations", [])
    ][:50]
    audit["all_citations_in_context"] = all_valid
    audit["explanation_summary"] = parsed.get("summary", "")[:500]
    audit["confidence"] = parsed.get("confidence")

    if not all_valid:
        audit["response_type"] = "invalid_output"
        audit["error_message"] = f"Citations not in context: {invalid_cites[:20]}"
        write_audit_entry(audit)
        return jsonify({
            "error": "citation guardrail failed",
            "invalid_citations": invalid_cites,
            "explanation": parsed,
        }), 422

    write_audit_entry(audit)
    return jsonify(parsed), 200


@app.route("/v1/health")
def health():
    return jsonify({"status": "ok"}), 200


def main():
    port = int(os.environ.get("PORT", 5002))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
