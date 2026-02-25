"""Unit tests for reasoning guardrails."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "reasoning"))

from guardrails import collect_context_ids, filter_steps_to_valid_citations, validate_citations


def test_collect_context_ids() -> None:
    subgraph = {
        "nodes": [
            {"id": "n1", "props": {"node_id": "did:abc"}},
            {"id": "n2", "props": {"event_id": "evt:1"}},
        ],
        "edges": [{"id": "e1", "source": "n1", "target": "n2"}],
    }
    ids = collect_context_ids(subgraph)
    assert "n1" in ids
    assert "n2" in ids
    assert "did:abc" in ids
    assert "evt:1" in ids
    assert "e1" in ids


def test_validate_citations_valid() -> None:
    steps = [{"step_number": 1, "claim": "x", "citations": ["n1", "did:abc"]}]
    context = {"n1", "did:abc"}
    valid, invalid = validate_citations(steps, context)
    assert valid is True
    assert len(invalid) == 0


def test_validate_citations_invalid() -> None:
    steps = [{"step_number": 1, "claim": "x", "citations": ["n1", "ghost"]}]
    context = {"n1"}
    valid, invalid = validate_citations(steps, context)
    assert valid is False
    assert "ghost" in invalid


def test_filter_steps_to_valid_citations() -> None:
    steps = [
        {"step_number": 1, "claim": "a", "citations": ["n1"]},
        {"step_number": 2, "claim": "b", "citations": ["n99"]},
    ]
    context = {"n1"}
    out = filter_steps_to_valid_citations(steps, context)
    assert len(out) == 1
    assert out[0]["step_number"] == 1
    assert out[0]["citations"] == ["n1"]
