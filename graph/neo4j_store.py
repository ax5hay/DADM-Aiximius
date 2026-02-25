"""
Neo4j graph store: create/merge nodes and relationships per DSO schema.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional  # noqa: F401

from neo4j import GraphDatabase

from schema import Device, Event, RiskScore, TimeWindow, Cluster, SurveillanceSubject


class Neo4jStore:
    def __init__(self, uri: str, user: str, password: str):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self._driver.close()

    def _run(self, query: str, **params):
        with self._driver.session() as session:
            return session.run(query, params)

    def run_list(self, query: str, **params) -> List[Dict[str, Any]]:
        """Run query and return list of record dicts (consumes result inside session)."""
        with self._driver.session() as session:
            result = session.run(query, params)
            return [dict(rec) for rec in result]

    def get_subgraph(
        self, node_id: str, hops: int = 2, window_sec: Optional[int] = None
    ) -> Dict[str, Any]:
        """Return nodes and edges around node_id within hops. window_sec ignored for now (filter in app)."""
        _ = window_sec
        with self._driver.session() as session:
            max_hops = min(hops, 5)
            q = """
            MATCH (start)
            WHERE start.node_id = $node_id OR start.event_id = $node_id
            WITH start LIMIT 1
            MATCH path = (start)-[*0..%d]-(x)
            RETURN path
            """ % max_hops
            result = session.run(q, node_id=node_id)
            nodes_seen: set = set()
            edges_seen: set = set()
            nodes_list: List[Dict[str, Any]] = []
            edges_list: List[Dict[str, Any]] = []
            for rec in result:
                path = rec.get("path")
                if path is None:
                    continue
                for node in path.nodes:
                    nid = node.element_id if hasattr(node, "element_id") else str(node.id)
                    if nid in nodes_seen:
                        continue
                    nodes_seen.add(nid)
                    props = dict(node)
                    for k, v in list(props.items()):
                        if hasattr(v, "isoformat") and callable(getattr(v, "isoformat")):
                            props[k] = v.isoformat()
                        elif v is not None and not isinstance(v, (str, int, float, bool)):
                            props[k] = str(v)
                    nodes_list.append({"id": nid, "labels": list(node.labels), "props": props})
                for rel in path.relationships:
                    eid = rel.element_id if hasattr(rel, "element_id") else str(rel.id)
                    if eid in edges_seen:
                        continue
                    edges_seen.add(eid)
                    s = rel.start_node.element_id if hasattr(rel.start_node, "element_id") else str(rel.start_node.id)
                    t = rel.end_node.element_id if hasattr(rel.end_node, "element_id") else str(rel.end_node.id)
                    edges_list.append({
                        "id": eid,
                        "type": rel.type,
                        "source": s,
                        "target": t,
                        "props": dict(rel),
                    })
            return {"nodes": nodes_list, "edges": edges_list}

    def ensure_indexes(self):
        """Create recommended indexes if not exist."""
        index_queries = [
            "CREATE INDEX device_node_id IF NOT EXISTS FOR (d:Device) ON (d.node_id)",
            "CREATE INDEX event_event_id IF NOT EXISTS FOR (e:Event) ON (e.event_id)",
            "CREATE INDEX event_ts IF NOT EXISTS FOR (e:Event) ON (e.ts)",
            "CREATE INDEX event_device_id IF NOT EXISTS FOR (e:Event) ON (e.device_id)",
            "CREATE INDEX risk_ts IF NOT EXISTS FOR (r:RiskScore) ON (r.ts)",
            "CREATE INDEX cluster_id IF NOT EXISTS FOR (c:Cluster) ON (c.cluster_id)",
            "CREATE INDEX time_window_id IF NOT EXISTS FOR (w:TimeWindow) ON (w.window_id)",
        ]
        for q in index_queries:
            try:
                self._run(q)
            except Exception:
                pass

    def upsert_device(self, d: Device):
        self._run(
            """
            MERGE (n:Device {node_id: $node_id})
            SET n.platform = $platform, n.last_seen = $last_seen
            SET n.first_seen = coalesce(n.first_seen, $first_seen)
            SET n.mesh_id = $mesh_id
            """,
            node_id=d.node_id,
            platform=d.platform,
            first_seen=d.first_seen.isoformat() if d.first_seen else None,
            last_seen=d.last_seen.isoformat() if d.last_seen else None,
            mesh_id=d.mesh_id,
        )

    def upsert_event(self, e: Event):
        self._run(
            """
            MERGE (ev:Event {event_id: $event_id})
            SET ev.kind = $kind, ev.ts = $ts, ev.device_id = $device_id, ev.payload_hash = $payload_hash
            WITH ev
            MATCH (d:Device {node_id: $device_id})
            MERGE (d)-[:REPORTS]->(ev)
            """,
            event_id=e.event_id,
            kind=e.kind,
            ts=e.ts.isoformat(),
            device_id=e.device_id,
            payload_hash=e.payload_hash,
        )

    def upsert_risk_score(self, r: RiskScore, link_to_device: bool = True):
        self._run(
            """
            MERGE (rs:RiskScore {id: $id})
            SET rs.score = $score, rs.level = $level, rs.ts = $ts,
                rs.window_start = $window_start, rs.window_end = $window_end, rs.source = $source
            """,
            id=r.id,
            score=r.score,
            level=r.level,
            ts=r.ts.isoformat(),
            window_start=r.window_start.isoformat(),
            window_end=r.window_end.isoformat(),
            source=r.source,
        )
        if link_to_device and r.source.startswith("did:"):
            self._run(
                """
                MATCH (d:Device {node_id: $device_id}), (rs:RiskScore {id: $id})
                MERGE (d)-[:HAS_RISK_IN]->(rs)
                """,
                device_id=r.source,
                id=r.id,
            )

    def upsert_time_window(self, w: TimeWindow):
        self._run(
            """
            MERGE (tw:TimeWindow {window_id: $window_id})
            SET tw.start_ts = $start_ts, tw.end_ts = $end_ts, tw.duration_sec = $duration_sec
            """,
            window_id=w.window_id,
            start_ts=w.start_ts.isoformat(),
            end_ts=w.end_ts.isoformat(),
            duration_sec=w.duration_sec,
        )

    def upsert_cluster(self, c: Cluster, device_ids: List[str]):
        self._run(
            """
            MERGE (cl:Cluster {cluster_id: $cluster_id})
            SET cl.created_at = $created_at, cl.method = $method, cl.size = $size
            """,
            cluster_id=c.cluster_id,
            created_at=c.created_at.isoformat(),
            method=c.method,
            size=c.size,
        )
        for did in device_ids:
            self._run(
                """
                MATCH (d:Device {node_id: $device_id}), (cl:Cluster {cluster_id: $cluster_id})
                MERGE (d)-[:MEMBER_OF]->(cl)
                """,
                device_id=did,
                cluster_id=c.cluster_id,
            )

    def add_communicates_with(self, device_id_a: str, device_id_b: str, first_ts: datetime, last_ts: datetime, byte_count: int = 0):
        self._run(
            """
            MATCH (a:Device {node_id: $a}), (b:Device {node_id: $b})
            MERGE (a)-[r:COMMUNICATES_WITH]->(b)
            SET r.first_ts = $first_ts, r.last_ts = $last_ts, r.byte_count = $byte_count
            """,
            a=device_id_a,
            b=device_id_b,
            first_ts=first_ts.isoformat(),
            last_ts=last_ts.isoformat(),
            byte_count=byte_count,
        )

    def add_tracked_as(self, device_id: str, subject_id: str):
        self._run(
            """
            MATCH (d:Device {node_id: $device_id})
            MERGE (s:SurveillanceSubject {subject_id: $subject_id})
            MERGE (d)-[:TRACKED_AS]->(s)
            """,
            device_id=device_id,
            subject_id=subject_id,
        )

    def add_propagates_to(self, source_risk_id: str, target_risk_id: str, weight: float):
        self._run(
            """
            MATCH (a:RiskScore {id: $sid}), (b:RiskScore {id: $tid})
            MERGE (a)-[r:PROPAGATES_TO]->(b)
            SET r.weight = $weight
            """,
            sid=source_risk_id,
            tid=target_risk_id,
            weight=weight,
        )
