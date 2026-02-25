"""
Unsupervised clustering: detect coordinated anomaly spikes (devices with high risk in same window).
See docs/DSO-ONTOLOGY.md §4.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import List, Set, Tuple

from neo4j import GraphDatabase

from schema import cluster_id


def run_clustering(
    driver,
    window_start: datetime,
    window_end: datetime,
    risk_threshold: float = 0.5,
    method: str = "risk_spike_correlation",
) -> List[Tuple[str, List[str]]]:
    """
    Find devices with risk >= threshold in window; group by connected component
    (same window + COMMUNICATES_WITH or shared cluster). Returns list of (cluster_id, [device_ids]).
    """
    with driver.session() as session:
        # Devices with high risk in this window
        r = session.run(
            """
            MATCH (d:Device)-[:HAS_RISK_IN]->(r:RiskScore)
            WHERE r.window_start >= $ws AND r.window_end <= $we AND r.score >= $thresh
            RETURN distinct d.node_id as device_id
            """,
            ws=window_start.isoformat(),
            we=window_end.isoformat(),
            thresh=risk_threshold,
        )
        high_risk_devices = [rec["device_id"] for rec in r]
        if len(high_risk_devices) <= 1:
            return []

        # Build edges: (d1, d2) if COMMUNICATES_WITH or same cluster
        r2 = session.run(
            """
            UNWIND $devices as d1
            MATCH (a:Device {node_id: d1})
            OPTIONAL MATCH (a)-[:COMMUNICATES_WITH]-(b:Device) WHERE b.node_id IN $devices
            WITH d1, collect(DISTINCT b.node_id) as comm
            OPTIONAL MATCH (a)-[:MEMBER_OF]->(c:Cluster)<-[:MEMBER_OF]-(b2:Device)
            WHERE b2.node_id IN $devices AND b2.node_id <> d1
            WITH d1, comm + collect(DISTINCT b2.node_id) as neighbors
            UNWIND [n IN neighbors WHERE n IS NOT NULL] as n
            RETURN d1, n
            """,
            devices=high_risk_devices,
        )
        adj: dict = defaultdict(set)
        for rec in r2:
            d1, n = rec["d1"], rec["n"]
            if n:
                adj[d1].add(n)
                adj[n].add(d1)
        for d in high_risk_devices:
            adj.setdefault(d, set())

        # Connected components
        seen: Set[str] = set()
        components: List[Set[str]] = []

        def dfs(node: str, comp: Set[str]):
            comp.add(node)
            seen.add(node)
            for neighbor in adj[node]:
                if neighbor not in seen:
                    dfs(neighbor, comp)

        for d in high_risk_devices:
            if d not in seen:
                comp = set()
                dfs(d, comp)
                if len(comp) >= 1:
                    components.append(comp)

        # Build cluster IDs and return (unique id per component)
        created = datetime.utcnow()
        out: List[Tuple[str, List[str]]] = []
        for i, comp in enumerate(components):
            method_hash = str(hash(tuple(sorted(comp)))[:8]) if comp else str(i)
            cid = cluster_id(created.timestamp(), f"{method}_{method_hash}")
            out.append((cid, list(comp)))
        return out
