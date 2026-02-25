"""
REST API for querying the defense graph (Flask).
Endpoints: ingest, risk propagation, clustering, dashboard queries.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

from flask import Flask, jsonify, request

from neo4j_store import Neo4jStore
from risk_propagation import propagate_risk
from clustering import run_clustering
from schema import (
    Device,
    Event,
    RiskScore,
    TimeWindow,
    Cluster,
    device_node_id,
    event_id,
    window_id,
    cluster_id as make_cluster_id,
)

app = Flask(__name__)

_INDEXES_ENSURED = False


def get_store() -> Neo4jStore:
    global _INDEXES_ENSURED
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "password")
    store = Neo4jStore(uri, user, password)
    if not _INDEXES_ENSURED:
        try:
            store.ensure_indexes()
            _INDEXES_ENSURED = True
        except Exception:
            pass
    return store


# ---- Ingest ----

@app.route("/api/v1/devices", methods=["POST"])
def ingest_device():
    body = request.get_json() or {}
    store = get_store()
    d = Device(
        node_id=body.get("node_id") or device_node_id(body["id"]),
        platform=body.get("platform", "unknown"),
        first_seen=body.get("first_seen"),
        last_seen=body.get("last_seen"),
        mesh_id=body.get("mesh_id"),
    )
    store.upsert_device(d)
    return jsonify({"status": "ok", "node_id": d.node_id}), 201


@app.route("/api/v1/events", methods=["POST"])
def ingest_event():
    body = request.get_json() or {}
    store = get_store()
    e = Event(
        event_id=body.get("event_id") or event_id(body["id"]),
        kind=body.get("kind", "process"),
        ts=datetime.fromisoformat(body["ts"].replace("Z", "+00:00")),
        device_id=body["device_id"],
        payload_hash=body.get("payload_hash"),
    )
    store.upsert_event(e)
    return jsonify({"status": "ok", "event_id": e.event_id}), 201


@app.route("/api/v1/risk_scores", methods=["POST"])
def ingest_risk_score():
    body = request.get_json() or {}
    store = get_store()
    r = RiskScore(
        id=body.get("id", f"risk_{body['device_id']}_{body.get('window_start', '')}"),
        score=float(body["score"]),
        level=body.get("level", "low"),
        ts=datetime.fromisoformat(body["ts"].replace("Z", "+00:00")),
        window_start=datetime.fromisoformat(body["window_start"].replace("Z", "+00:00")),
        window_end=datetime.fromisoformat(body["window_end"].replace("Z", "+00:00")),
        source=body.get("source", body["device_id"]),
    )
    store.upsert_risk_score(r)
    return jsonify({"status": "ok", "id": r.id}), 201


@app.route("/api/v1/ingest/batch", methods=["POST"])
def ingest_batch():
    """Batch ingest devices, events, risk_scores. Body: { devices: [], events: [], risk_scores: [] }."""
    body = request.get_json() or {}
    store = get_store()
    devices = body.get("devices", [])
    events = body.get("events", [])
    risk_scores = body.get("risk_scores", [])
    for d in devices:
        dev = Device(
            node_id=d.get("node_id") or device_node_id(d.get("id", "")),
            platform=d.get("platform", "unknown"),
            first_seen=datetime.fromisoformat(d["first_seen"].replace("Z", "+00:00")) if d.get("first_seen") else None,
            last_seen=datetime.fromisoformat(d["last_seen"].replace("Z", "+00:00")) if d.get("last_seen") else None,
            mesh_id=d.get("mesh_id"),
        )
        store.upsert_device(dev)
    for e in events:
        ev = Event(
            event_id=e.get("event_id") or event_id(e.get("id", "")),
            kind=e.get("kind", "process"),
            ts=datetime.fromisoformat(e["ts"].replace("Z", "+00:00")),
            device_id=e["device_id"],
            payload_hash=e.get("payload_hash"),
        )
        store.upsert_event(ev)
    for r in risk_scores:
        rs = RiskScore(
            id=r.get("id", f"risk_{r.get('device_id', '')}_{r.get('ts', '')}"),
            score=float(r["score"]),
            level=r.get("level", "low"),
            ts=datetime.fromisoformat(r["ts"].replace("Z", "+00:00")),
            window_start=datetime.fromisoformat(r["window_start"].replace("Z", "+00:00")),
            window_end=datetime.fromisoformat(r["window_end"].replace("Z", "+00:00")),
            source=r.get("source", r.get("device_id", "")),
        )
        store.upsert_risk_score(rs)
    return jsonify({
        "status": "ok",
        "devices": len(devices),
        "events": len(events),
        "risk_scores": len(risk_scores),
    }), 201


@app.route("/api/v1/subgraph")
def get_subgraph():
    """Return subgraph around node_id for reasoning layer. Query: node_id, hops (default 2), window_sec (optional)."""
    node_id = request.args.get("node_id") or request.args.get("node")
    if not node_id:
        return jsonify({"error": "missing node_id"}), 400
    hops = int(request.args.get("hops", 2))
    window_sec = request.args.get("window_sec", type=int)
    store = get_store()
    data = store.get_subgraph(node_id, hops=hops, window_sec=window_sec)
    return jsonify(data), 200


# ---- Risk propagation ----

@app.route("/api/v1/risk/propagate", methods=["POST"])
def trigger_propagate():
    body = request.get_json() or {}
    store = get_store()
    ws = body.get("window_start") or (datetime.utcnow() - timedelta(hours=1)).isoformat()
    we = body.get("window_end") or datetime.utcnow().isoformat()
    window_start = datetime.fromisoformat(ws.replace("Z", "+00:00"))
    window_end = datetime.fromisoformat(we.replace("Z", "+00:00"))
    decay = float(body.get("decay", 0.7))
    max_hops = int(body.get("max_hops", 2))
    scores = propagate_risk(store._driver, window_start, window_end, decay, max_hops)
    return jsonify({"status": "ok", "propagated_scores": scores}), 200


# ---- Clustering ----

@app.route("/api/v1/clusters/run", methods=["POST"])
def trigger_clustering():
    body = request.get_json() or {}
    store = get_store()
    ws = body.get("window_start") or (datetime.utcnow() - timedelta(hours=1)).isoformat()
    we = body.get("window_end") or datetime.utcnow().isoformat()
    window_start = datetime.fromisoformat(ws.replace("Z", "+00:00"))
    window_end = datetime.fromisoformat(we.replace("Z", "+00:00"))
    threshold = float(body.get("risk_threshold", 0.5))
    clusters = run_clustering(store._driver, window_start, window_end, threshold)
    created = datetime.utcnow()
    for cid, device_ids in clusters:
        c = Cluster(cluster_id=cid, created_at=created, method="risk_spike_correlation", size=len(device_ids))
        store.upsert_cluster(c, device_ids)
    return jsonify({"status": "ok", "clusters": [{"cluster_id": cid, "devices": devs} for cid, devs in clusters]}), 200


# ---- Dashboard queries ----

@app.route("/api/v1/dashboard/high_risk_devices")
def dashboard_high_risk():
    """High-risk devices in last 24h."""
    store = get_store()
    rows = store.run_list(
        """
        MATCH (d:Device)-[:HAS_RISK_IN]->(r:RiskScore)
        WHERE r.window_end >= datetime() - duration('P1D') AND r.level IN ['high', 'medium']
        RETURN d.node_id as node_id, d.platform as platform, r.score as score, r.window_end as window_end
        ORDER BY r.score DESC
        LIMIT 100
        """
    )
    return jsonify({"data": rows}), 200


@app.route("/api/v1/dashboard/coordinated_spikes")
def dashboard_coordinated_spikes():
    """Devices in same cluster with high risk in same window."""
    store = get_store()
    rows = store.run_list(
        """
        MATCH (d:Device)-[:MEMBER_OF]->(c:Cluster)<-[:MEMBER_OF]-(d2:Device)
        MATCH (d)-[:HAS_RISK_IN]->(r:RiskScore), (d2)-[:HAS_RISK_IN]->(r2:RiskScore)
        WHERE r.window_start = r2.window_start AND r.score >= 0.5 AND r2.score >= 0.5
        RETURN c.cluster_id as cluster_id, collect(d.node_id) as devices, r.window_start as window_start
        LIMIT 50
        """
    )
    return jsonify({"data": rows}), 200


@app.route("/api/v1/dashboard/surveillance_summary")
def dashboard_surveillance_summary():
    """Non-intrusive: count devices and risk stats per SurveillanceSubject (last 24h)."""
    store = get_store()
    rows = store.run_list(
        """
        MATCH (d:Device)-[:TRACKED_AS]->(s:SurveillanceSubject)
        OPTIONAL MATCH (d)-[:HAS_RISK_IN]->(r:RiskScore)
        WHERE r.window_end >= datetime() - duration('P1D')
        RETURN s.subject_id as subject_id, s.label as label,
               count(DISTINCT d) as devices,
               count(r) as risk_events,
               avg(r.score) as avg_risk
        """
    )
    return jsonify({"data": rows}), 200


@app.route("/api/v1/dashboard/event_volume")
def dashboard_event_volume():
    """Event volume by kind and device (last 6h)."""
    store = get_store()
    rows = store.run_list(
        """
        MATCH (d:Device)-[:REPORTS]->(e:Event)
        WHERE e.ts >= datetime() - duration('PT6H')
        RETURN d.node_id as node_id, e.kind as kind, count(e) as cnt
        ORDER BY cnt DESC
        LIMIT 200
        """
    )
    return jsonify({"data": rows}), 200


@app.route("/api/v1/health")
def health():
    return jsonify({"status": "ok"}), 200


def main():
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
