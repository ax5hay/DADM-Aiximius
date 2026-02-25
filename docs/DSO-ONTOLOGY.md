# Defense Systems Ontology (DSO) & Graph Engine

**Purpose:** Correlate anomalies across distributed nodes in the DADM mesh.  
**Scope:** Devices, events, risk scores, time windows; risk propagation; cluster detection for coordinated anomaly spikes; non-intrusive surveillance tracking; stable node IDs.

---

## 1. Ontology Schema

### 1.1 Core Classes (Entities)

| Class | Description | Key attributes |
|-------|-------------|----------------|
| **Device** | A physical or virtual endpoint (agent host). | `node_id` (stable ID), `platform`, `first_seen`, `last_seen` |
| **Event** | A single observation (process, network, file, privilege). | `event_id`, `kind`, `ts`, `device_id` (FK) |
| **RiskScore** | Anomaly score for an event or device in a time window. | `score`, `level`, `ts`, `window_start`, `window_end` |
| **TimeWindow** | A bounded time interval for aggregation. | `window_id`, `start_ts`, `end_ts`, `duration_sec` |
| **Cluster** | A set of devices or events grouped by similarity/coordination. | `cluster_id`, `created_at`, `method` |
| **SurveillanceSubject** | Non-intrusive tracking target (e.g. device or role). | `subject_id`, `label`, `policy` |

### 1.2 Relationships (Object Properties)

| Relation | Domain | Range | Description |
|----------|--------|-------|-------------|
| **reports** | Device | Event | Device produced this event. |
| **hasRiskIn** | Event \| Device | RiskScore | Event/device has a risk score in a window. |
| **inWindow** | Event \| RiskScore | TimeWindow | Event or score falls in this window. |
| **memberOf** | Device \| Event | Cluster | Device/event belongs to this cluster. |
| **communicatesWith** | Device | Device | Observed network/flow between devices. |
| **sameClusterAs** | Device | Device | Same cluster (derived). |
| **trackedAs** | Device | SurveillanceSubject | Device is tracked under this subject (non-intrusive). |
| **propagatesTo** | RiskScore | RiskScore | Risk propagated from one node/window to another. |

### 1.3 Node ID Scheme

- **Device node_id:** Stable, opaque ID (e.g. UUID or hash of attested device key). Never re-used across devices. Format: `did:<uuid>` or `did:<hash>`.
- **Event event_id:** Unique per event; format `evt:<uuid>`.
- **Cluster cluster_id:** Format `clu:<timestamp>:<hash>`.
- **TimeWindow window_id:** Format `win:<start_ts>:<duration_sec>`.
- **SurveillanceSubject subject_id:** Format `subj:<label>:<id>`.

---

## 2. Graph Data Model (Neo4j/Cypher)

### 2.1 Node Labels and Properties

```cypher
(:Device {
  node_id: string,      // primary key
  platform: string,     // android | ios | windows | macos | linux
  first_seen: datetime,
  last_seen: datetime,
  mesh_id: string       // optional mesh peer id
})

(:Event {
  event_id: string,
  kind: string,         // process | network | file_integrity | privilege
  ts: datetime,
  device_id: string,    // FK to Device.node_id
  payload_hash: string  // optional; no raw payload in graph
})

(:RiskScore {
  id: string,
  score: float,         // [0,1]
  level: string,        // low | medium | high
  ts: datetime,
  window_start: datetime,
  window_end: datetime,
  source: string        // event_id or device_id
})

(:TimeWindow {
  window_id: string,
  start_ts: datetime,
  end_ts: datetime,
  duration_sec: int
})

(:Cluster {
  cluster_id: string,
  created_at: datetime,
  method: string,       // e.g. risk_spike_correlation | dbscan
  size: int
})

(:SurveillanceSubject {
  subject_id: string,
  label: string,
  policy: string        // e.g. non_intrusive
})
```

### 2.2 Relationship Types

```cypher
(Device)-[:REPORTS]->(Event)
(Device)-[:HAS_RISK_IN]->(RiskScore)
(Event)-[:HAS_RISK_IN]->(RiskScore)
(Event)-[:IN_WINDOW]->(TimeWindow)
(RiskScore)-[:IN_WINDOW]->(TimeWindow)
(Device)-[:MEMBER_OF]->(Cluster)
(Event)-[:MEMBER_OF]->(Cluster)
(Device)-[:COMMUNICATES_WITH {first_ts, last_ts, byte_count}]->(Device)
(Device)-[:TRACKED_AS]->(SurveillanceSubject)
(RiskScore)-[:PROPAGATES_TO {weight}]->(RiskScore)
(Device)-[:SAME_CLUSTER_AS]-(Device)  // derived from MEMBER_OF
```

### 2.3 Indexes (recommended)

```cypher
CREATE INDEX device_node_id FOR (d:Device) ON (d.node_id);
CREATE INDEX event_event_id FOR (e:Event) ON (e.event_id);
CREATE INDEX event_ts FOR (e:Event) ON (e.ts);
CREATE INDEX event_device_id FOR (e:Event) ON (e.device_id);
CREATE INDEX risk_ts FOR (r:RiskScore) ON (r.ts);
CREATE INDEX risk_window FOR (r:RiskScore) ON (r.window_start, r.window_end);
CREATE INDEX cluster_id FOR (c:Cluster) ON (c.cluster_id);
CREATE INDEX time_window_id FOR (w:TimeWindow) ON (w.window_id);
```

---

## 3. Risk Propagation Algorithm

**Goal:** Propagate risk along graph edges (device communication, shared cluster, temporal proximity) so that correlated nodes receive an adjusted risk signal.

**Steps:**

1. **Seed:** For each `RiskScore` in the current time window, set `propagated_score(n) = score(n)`.
2. **Neighbors:** For each device with risk, get neighbors via `COMMUNICATES_WITH` or `SAME_CLUSTER_AS` within the same or adjacent time window.
3. **Propagation rule:**  
   `propagated_score(neighbor) = max(propagated_score(neighbor), decay * propagated_score(source))`  
   where `decay in (0,1)` (e.g. 0.7) and optionally weight by edge strength (e.g. byte_count, recency).
4. **Iterate:** Repeat for K hops (e.g. K=2) or until convergence (delta below threshold).
5. **Persist:** Write back `PROPAGATES_TO` edges with `weight = decay^hop` and optionally update a materialized `aggregated_risk` on `Device` nodes.

**Pseudocode:**

```
function propagate_risk(G, risk_scores, decay=0.7, max_hops=2):
  for each (node, score) in risk_scores:
    set current[node] = score
  for hop = 1 to max_hops:
    next = copy(current)
    for each (node, score) where score > 0:
      for each neighbor in G.neighbors(node) via COMMUNICATES_WITH or SAME_CLUSTER_AS:
        next[neighbor] = max(next[neighbor], decay * score)
        create or update PROPAGATES_TO(node -> neighbor, weight=decay^hop)
    current = next
  return current
```

---

## 4. Clustering Algorithm (Unsupervised)

**Goal:** Detect groups of devices or events that show coordinated anomaly spikes (e.g. same time window, similar risk profile).

**Options:**

1. **Time-based + risk spike:** Group devices that have a risk score above threshold in the same time window. Cluster = set of such devices per window.
2. **DBSCAN on (time, risk, device_id hash):** Treat each (device, window) as a point (e.g. `(window_center_ts, max_risk, device_hash)`); run DBSCAN; clusters = connected components.
3. **Graph-based:** Run connected components on subgraph induced by “high risk in window W” nodes and `COMMUNICATES_WITH` edges.

**Recommended (hybrid):**

- **Phase 1:** Select (device, window) with `risk_score >= threshold` (e.g. 0.5).
- **Phase 2:** Build similarity matrix: `sim(d1, d2) = 1` if same window and (d1, d2) have `COMMUNICATES_WITH` or share a cluster in last 24h; else 0.
- **Phase 3:** Run connected components or label propagation to get cluster IDs. Create `Cluster` nodes and `MEMBER_OF` edges.

**Output:** New `Cluster` nodes and `(Device)-[:MEMBER_OF]->(Cluster)`; optional `(Device)-[:SAME_CLUSTER_AS]-(Device)` for fast lookup.

---

## 5. Personal Surveillance Tracking (Non-Intrusive)

- **SurveillanceSubject:** Represents a tracking target (e.g. “role:admin”, “zone:building-A”). No PII in the graph; only labels and policy.
- **TRACKED_AS:** Links a `Device` to a `SurveillanceSubject` when policy assigns that device to the subject (e.g. by zone or role).
- **Non-intrusive:** Only aggregated counts, risk levels, and cluster membership are stored; no raw logs or content. Queries answer “how many devices in subject X had high risk in window W?” not “what did user X do?”.
- **Dashboard:** Count of devices per subject, risk distribution per subject over time, clusters that intersect a subject.

---

## 6. API for Querying Defense Graph

See implementation in `graph/` for:

- **Ingest:** POST devices, events, risk scores, time windows; create/merge nodes and relationships.
- **Risk propagation:** POST trigger propagation for a given window; GET propagated risk per device.
- **Clustering:** POST run clustering for a window; GET clusters and members.
- **Queries:** GET devices by risk range, events by device and time, clusters by time, surveillance stats per subject.
- **Example dashboard queries:** See section 7 and `graph/examples/dashboard_queries.cypher`.

---

## 7. Example Dashboard Queries

**High-risk devices in last 24h:**
```cypher
MATCH (d:Device)-[:HAS_RISK_IN]->(r:RiskScore)
WHERE r.window_end >= datetime() - duration('P1D') AND r.level = 'high'
RETURN d.node_id, d.platform, r.score, r.window_end
ORDER BY r.score DESC
```

**Coordinated spike: devices in same cluster with high risk in same window:**
```cypher
MATCH (d:Device)-[:MEMBER_OF]->(c:Cluster)<-[:MEMBER_OF]-(d2:Device)
MATCH (d)-[:HAS_RISK_IN]->(r:RiskScore), (d2)-[:HAS_RISK_IN]->(r2:RiskScore)
WHERE r.window_start = r2.window_start AND r.score >= 0.5 AND r2.score >= 0.5
RETURN c.cluster_id, collect(d.node_id) as devices, r.window_start
```

**Risk propagation path from device A:**
```cypher
MATCH path = (d:Device {node_id: $device_id})-[:HAS_RISK_IN|PROPAGATES_TO*1..3]->(r:RiskScore)
RETURN path
```

**Surveillance summary per subject (non-intrusive):**
```cypher
MATCH (d:Device)-[:TRACKED_AS]->(s:SurveillanceSubject)
OPTIONAL MATCH (d)-[:HAS_RISK_IN]->(r:RiskScore)
WHERE r.window_end >= datetime() - duration('P1D')
RETURN s.subject_id, s.label, count(DISTINCT d) as devices, count(r) as risk_events, avg(r.score) as avg_risk
```

**Event volume by kind and device (last 6h):**
```cypher
MATCH (d:Device)-[:REPORTS]->(e:Event)
WHERE e.ts >= datetime() - duration('PT6H')
RETURN d.node_id, e.kind, count(e) as cnt
ORDER BY cnt DESC
```

---

## Document Control

- **Created:** 2025-02-26  
- **Status:** Design approved  
- **Implementation:** `graph/` (schema, propagation, clustering, API, example queries).
