"""
Risk propagation: propagate risk scores along COMMUNICATES_WITH and SAME_CLUSTER_AS (MEMBER_OF).
See docs/DSO-ONTOLOGY.md §3.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from neo4j import GraphDatabase


def propagate_risk(
    driver,
    window_start: datetime,
    window_end: datetime,
    decay: float = 0.7,
    max_hops: int = 2,
) -> Dict[str, float]:
    """
    Read risk scores in window, propagate along COMMUNICATES_WITH and cluster membership.
    Returns dict device_id -> propagated_score.
    """
    with driver.session() as session:
        # Seed: device -> risk in this window
        r = session.run(
            """
            MATCH (d:Device)-[:HAS_RISK_IN]->(r:RiskScore)
            WHERE r.window_start >= $ws AND r.window_end <= $we
            RETURN d.node_id as device_id, max(r.score) as score
            """,
            ws=window_start.isoformat(),
            we=window_end.isoformat(),
        )
        current: Dict[str, float] = {rec["device_id"]: float(rec["score"]) for rec in r}

        if not current:
            return {}

        for hop in range(1, max_hops + 1):
            next_scores = dict(current)
            for device_id, score in list(current.items()):
                if score <= 0:
                    continue
                propagated = score * (decay ** hop)
                # Neighbors: COMMUNICATES_WITH or same cluster (MEMBER_OF same Cluster)
                r2 = session.run(
                    """
                    MATCH (d:Device {node_id: $device_id})
                    OPTIONAL MATCH (d)-[:COMMUNICATES_WITH]-(other:Device)
                    WITH collect(DISTINCT other.node_id) as comm
                    OPTIONAL MATCH (d)-[:MEMBER_OF]->(c:Cluster)<-[:MEMBER_OF]-(other2:Device)
                    WITH comm + collect(DISTINCT other2.node_id) as all_neighbors
                    UNWIND all_neighbors as n
                    RETURN distinct n WHERE n IS NOT NULL
                    """,
                    device_id=device_id,
                )
                for rec in r2:
                    n = rec.get("n")
                    if n and n != device_id:
                        next_scores[n] = max(next_scores.get(n, 0), propagated)
            current = next_scores

        # Persist PROPAGATES_TO edges (source risk -> neighbor risk) for first-hop only for simplicity
        # In full impl would create RiskScore nodes for propagated values or store on Device
        return current
