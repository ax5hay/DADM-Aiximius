# DADM User Flow and Output

How the system runs end-to-end and what the end user sees (logs, API responses, dashboards).

---

## 1. High-level flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  END USER / OPERATOR                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         │ 1. Start stack         2. Run agent (with uplink)      3. Query
         ▼                         ▼                                ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────────────┐
│ docker compose  │    │ dadm-agent      │    │ Graph API (dashboard)            │
│ up -d           │    │ (daemon or      │───▶│ Reasoning API (/v1/reason)      │
│                 │    │  single shot)   │    │ Neo4j Browser (optional)         │
└────────┬────────┘    └────────┬────────┘    └─────────────────────────────────┘
         │                      │
         │                      │ POST /api/v1/devices, /events, /risk_scores
         ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│ Neo4j           │◀───│ Graph API :5001  │
│ Fusion :5000    │    │ Reasoning :5002  │
│ Mesh :5003      │    │                  │
└─────────────────┘    └─────────────────┘
```

- **Operator** starts the stack, runs the agent (with uplink to Graph), then uses **Graph dashboard** and **Reasoning** to see devices, risk, and explanations.
- **Agent** (on a device or VM) collects events, scores risk, and when uplink is enabled **POSTs** device, events, and risk scores to the Graph API.
- **Graph API** stores everything in Neo4j and exposes **dashboard** and **subgraph** endpoints.
- **Reasoning** service uses the graph (subgraph) to answer natural-language questions and returns **step-by-step explanations with citations**.

---

## 2. Starting the system (what the user runs)

```bash
# Terminal 1: start backend
docker compose up -d

# Wait for services (e.g. 30s), then optionally run agent with uplink
# Terminal 2: run agent (single shot, with uplink to Graph)
cd agent && cargo build --release
DADM_UPLINK_ENABLED=true \
DADM_UPLINK_ENDPOINT=http://localhost:5001 \
DADM_DEVICE_ID=laptop-01 \
./target/release/dadm-agent
```

Or **daemon mode** (runs forever, reports every N seconds): set in `config.json` e.g. `"process_interval_secs": 300`, then run the same command; the agent will log each cycle and uplink after each run.

---

## 3. What the end user sees

### 3.1 Agent output (terminal / logs)

**Single-shot run (default), JSON logs** (e.g. `config.log.json: true`):

```json
{"timestamp":"2025-02-26T12:00:00.000000Z","level":"INFO","target":"dadm_agent","message":"DADM agent starting","data_dir":".dadm"}
{"timestamp":"2025-02-26T12:00:00.001000Z","level":"INFO","target":"dadm_agent","message":"collected events","count":42}
{"timestamp":"2025-02-26T12:00:00.050000Z","level":"INFO","target":"dadm_agent","message":"risk result","event_id":"abc-123","score":0.72,"level":"Medium"}
{"timestamp":"2025-02-26T12:00:00.051000Z","level":"INFO","target":"dadm_agent","message":"uplink risk reported","score":0.72,"level":"Medium"}
{"timestamp":"2025-02-26T12:00:00.052000Z","level":"INFO","target":"dadm_agent","message":"DADM agent cycle complete"}
```

**Daemon mode** (same style, repeated every interval, plus uplink confirmations):

```json
{"message":"daemon mode (Ctrl+C to stop)","interval_secs":300}
{"message":"collected events","count":38}
{"message":"uplink device registered","device_id":"did:laptop-01"}
{"message":"uplink risk reported","score":0.45,"level":"Low"}
...
{"message":"DADM agent stopping"}
```

So the **end user** (or log aggregator) sees: startup, event counts per cycle, risk results when not Low, uplink registration once, and uplink risk reported each cycle.

---

### 3.2 Graph API — dashboard (what the operator sees in the UI/API)

The operator (or a dashboard app) calls the Graph API. Example responses:

**High-risk devices (last 24h)**  
`GET http://localhost:5001/api/v1/dashboard/high_risk_devices`

```json
{
  "data": [
    {
      "node_id": "did:laptop-01",
      "platform": "macos",
      "score": 0.72,
      "window_end": "2025-02-26T12:00:00.000Z"
    },
    {
      "node_id": "did:workstation-02",
      "platform": "linux",
      "score": 0.91,
      "window_end": "2025-02-26T11:55:00.000Z"
    }
  ]
}
```

**Event volume by device and kind (last 6h)**  
`GET http://localhost:5001/api/v1/dashboard/event_volume`

```json
{
  "data": [
    { "node_id": "did:laptop-01", "kind": "process", "cnt": 120 },
    { "node_id": "did:laptop-01", "kind": "network", "cnt": 45 },
    { "node_id": "did:workstation-02", "kind": "process", "cnt": 98 }
  ]
}
```

**Coordinated spikes** (devices in same cluster with high risk in same window)  
`GET http://localhost:5001/api/v1/dashboard/coordinated_spikes`

```json
{
  "data": [
    {
      "cluster_id": "clu:1730012400:default",
      "devices": ["did:laptop-01", "did:workstation-02"],
      "window_start": "2025-02-26T11:00:00.000Z"
    }
  ]
}
```

**Surveillance summary** (if devices are linked to SurveillanceSubject)  
`GET http://localhost:5001/api/v1/dashboard/surveillance_summary`

```json
{
  "data": [
    {
      "subject_id": "subj:building-a:floor-1",
      "label": "building-a",
      "devices": 5,
      "risk_events": 12,
      "avg_risk": 0.35
    }
  ]
}
```

So the **end user / operator** sees: which devices are high risk, event volumes per device and kind, clusters with coordinated risk, and (if used) surveillance summaries.

---

### 3.3 Reasoning API — natural-language explanation (what the operator sees)

Operator asks: *“Why is device did:laptop-01 high risk?”*

**Request:**

```bash
curl -s -X POST http://localhost:5002/v1/reason \
  -H "Content-Type: application/json" \
  -d '{"query": "Why is device did:laptop-01 high risk?", "node_id": "did:laptop-01", "hops": 2}'
```

**Response (stub LLM or real LLM):**

```json
{
  "explanation_steps": [
    {
      "step_number": 1,
      "claim": "Device did:laptop-01 has a risk score of 0.72 in the last window.",
      "citations": ["did:laptop-01", "risk_did:laptop-01_1730012400000"]
    },
    {
      "step_number": 2,
      "claim": "The device reported multiple process and network events in the same window.",
      "citations": ["evt:abc-123", "evt:def-456"]
    }
  ],
  "summary": "Device did:laptop-01 is elevated due to recent risk score 0.72 and elevated process/network activity in the same time window.",
  "confidence": 0.85,
  "confidence_justification": "Based on risk score and event counts in the subgraph; no external threat intel."
}
```

So the **end user** sees: a short, step-by-step explanation with citations to graph nodes, a summary, and a confidence score.

---

### 3.4 Health and ingest (operator / automation)

- **Health**  
  `GET http://localhost:5001/api/v1/health` → `{"status":"ok"}`  
  Same idea for Fusion, Reasoning, Mesh (see RUNBOOK).

- **Batch ingest** (e.g. bulk load)  
  `POST http://localhost:5001/api/v1/ingest/batch` with body:

  ```json
  {
    "devices": [{"node_id": "did:new-1", "platform": "windows", "first_seen": "2025-02-26T12:00:00Z", "last_seen": "2025-02-26T12:00:00Z"}],
    "events": [],
    "risk_scores": []
  }
  ```
  Response: `{"status":"ok","devices":1,"events":0,"risk_scores":0}`.

---

## 4. End-to-end flow summary

| Step | Who / What | Action | What the user sees |
|------|------------|--------|--------------------|
| 1 | Operator | `docker compose up -d` | Containers start; Neo4j, Fusion, Graph, Reasoning, Mesh up |
| 2 | Operator | Run agent with `DADM_UPLINK_ENABLED=true`, `DADM_UPLINK_ENDPOINT=http://localhost:5001` | Agent logs: “DADM agent starting”, “collected events”, “uplink device registered”, “uplink risk reported”, “cycle complete” (or repeated in daemon) |
| 3 | Graph API | Receives POSTs from agent | Devices, events, risk scores stored in Neo4j |
| 4 | Operator / Dashboard | `GET .../dashboard/high_risk_devices`, `event_volume`, etc. | JSON tables: high-risk devices, event counts, coordinated spikes, surveillance summary |
| 5 | Operator | `POST .../v1/reason` with query and `node_id` | JSON explanation: steps, citations, summary, confidence |
| 6 | (Optional) Neo4j Browser | Open http://localhost:7474, run Cypher | Raw graph: Device, Event, RiskScore, Cluster nodes and relationships |

So when the system is up and running, the **end user** sees: **agent logs** in the terminal, **dashboard JSON** from the Graph API (or a UI that calls it), and **reasoning explanations** from the Reasoning API; optionally they can inspect the graph in Neo4j Browser.
