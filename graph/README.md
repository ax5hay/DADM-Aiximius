# DSO Graph Engine — Defense Systems Ontology

Correlate anomalies across distributed DADM nodes using a graph database (Neo4j). Implements the [Defense Systems Ontology (DSO)](../docs/DSO-ONTOLOGY.md): devices, events, risk scores, time windows, risk propagation, cluster detection, and non-intrusive surveillance tracking.

## Features

- **Ontology schema:** Device, Event, RiskScore, TimeWindow, Cluster, SurveillanceSubject; stable node IDs.
- **Graph store:** Neo4j with indexes; ingest devices, events, risk scores; relationships REPORTS, HAS_RISK_IN, MEMBER_OF, COMMUNICATES_WITH, TRACKED_AS, PROPAGATES_TO.
- **Risk propagation:** Propagate risk along COMMUNICATES_WITH and cluster membership; configurable decay and max hops.
- **Clustering:** Unsupervised grouping of devices with coordinated anomaly spikes (same window, high risk, connected by communication or cluster).
- **API:** REST endpoints for ingest, propagation, clustering, and dashboard queries.
- **Dashboard queries:** High-risk devices, coordinated spikes, surveillance summary, event volume.

## Requirements

- Python 3.10+
- Neo4j 5.x (local or Docker)

## Quick start

```bash
# Start Neo4j (Docker)
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:5

cd graph
pip install -r requirements.txt
export NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=password
python api.py
```

- **Ingest:** `POST /api/v1/devices`, `POST /api/v1/events`, `POST /api/v1/risk_scores` with JSON bodies (see schema).
- **Propagate risk:** `POST /api/v1/risk/propagate` with `window_start`, `window_end`, `decay`, `max_hops`.
- **Run clustering:** `POST /api/v1/clusters/run` with `window_start`, `window_end`, `risk_threshold`.
- **Dashboard:** `GET /api/v1/dashboard/high_risk_devices`, `coordinated_spikes`, `surveillance_summary`, `event_volume`.

## Example Cypher

See `examples/dashboard_queries.cypher` for copy-paste queries (high-risk devices, coordinated spikes, propagation paths, surveillance summary, event volume).

## Node IDs

- Device: `did:<uuid>` or `did:<hash>`
- Event: `evt:<uuid>`
- Cluster: `clu:<timestamp>:<method_hash>`
- TimeWindow: `win:<start_ts>:<duration_sec>`
- SurveillanceSubject: `subj:<label>:<id>`
