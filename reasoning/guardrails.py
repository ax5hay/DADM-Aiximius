"""Citation guardrail: ensure every citation in the explanation exists in the subgraph context."""

from __future__ import annotations

from typing import Any, Dict, List, Set


def collect_context_ids(subgraph: Dict[str, Any]) -> Set[str]:
    """Collect all node ids and edge ids from subgraph (nodes[].id, nodes[].props.node_id, edges[].id)."""
    ids: Set[str] = set()
    for node in subgraph.get("nodes", []):
        nid = node.get("id")
        if nid:
            ids.add(str(nid))
        props = node.get("props") or {}
        if "node_id" in props:
            ids.add(str(props["node_id"]))
        if "event_id" in props:
            ids.add(str(props["event_id"]))
        if "id" in props:
            ids.add(str(props["id"]))
    for edge in subgraph.get("edges", []):
        eid = edge.get("id")
        if eid:
            ids.add(str(eid))
    return ids


def validate_citations(explanation_steps: List[Dict[str, Any]], context_ids: Set[str]) -> tuple[bool, List[str]]:
    """
    Return (all_valid, list_of_invalid_citation_ids).
    If a step cites an id not in context_ids, it's invalid.
    """
    invalid: List[str] = []
    for step in explanation_steps:
        for c in step.get("citations", []):
            cid = str(c).strip()
            if cid and cid not in context_ids:
                invalid.append(cid)
    return (len(invalid) == 0, invalid)


def filter_steps_to_valid_citations(
    explanation_steps: List[Dict[str, Any]], context_ids: Set[str]
) -> List[Dict[str, Any]]:
    """Return steps with only citations that exist in context; drop steps that would have no citations."""
    out: List[Dict[str, Any]] = []
    for step in explanation_steps:
        valid_cites = [c for c in step.get("citations", []) if str(c).strip() in context_ids]
        if valid_cites:
            out.append({**step, "citations": valid_cites})
    return out
