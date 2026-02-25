# DADM Implementation Plan — From Design to Operational System

**Goal:** Turn design docs and placeholder/example code into a functioning system: agent runs continuously and can push to graph/fusion; fusion exports correct ONNX; graph is populated and queryable; reasoning service and mesh have runnable implementations; full stack runs via Docker Compose.

---

## Deep-dive summary

| Area | Current state | Gaps |
|------|----------------|------|
| **Agent** | One-shot main; collectors, features, model, storage, risk work. Config has uplink but unused. | No daemon loop; no uplink client; exits after one cycle. |
| **Training** | train.py, export_onnx.py (ScoreWrapper), quantize, drift, explain work. | No single “produce model for agent” script; export is correct. |
| **Federated** | Server: config, updates (decrypt), aggregate, model v0 bootstrap, /model, /rollback. Client: gradient push. | Server exports ONNX with **forward** not **anomaly_score** — agent expects [1,1] score. |
| **Graph** | Neo4j store, propagation, clustering, Flask API, ingest + dashboard. | No subgraph export for reasoning; no batch ingest; ensure_indexes not called on startup; new store per request. |
| **Mesh** | OpenAPI spec only. | No enrollment or CRL server implementation. |
| **Reasoning** | JSON schemas only. | No LLM service, no prompt builder, no citation guardrail, no audit writer. |
| **Deploy** | Terraform (placeholder resources), Ansible (FIPS, audit, model verify stubs). | No “run everything” stack; Ansible handlers may reboot. |

---

## Phase 1 — Agent daemon and uplink

1. **Agent daemon loop**  
   - Run collection → features → inference → risk → store in a loop with configurable interval (e.g. `collectors.process_interval_secs`).  
   - Support graceful shutdown (Ctrl+C / SIGTERM).  
   - Config: optional `config_path` from env `DADM_CONFIG_PATH`.

2. **Uplink client (Rust)**  
   - When `uplink.enabled` and `uplink.endpoint` are set, after each cycle POST to uplink:  
     - Register device once (PUT/POST device with node_id, platform).  
     - POST events (id, kind, ts, device_id, no raw payload; optional payload_hash).  
     - POST risk_scores (device_id, score, level, window_start, window_end).  
   - Use `reqwest` (or `ureq`) with TLS; timeout and retry (e.g. 3 retries, exponential backoff).  
   - If endpoint is graph API base URL, use `POST /api/v1/devices`, `POST /api/v1/events`, `POST /api/v1/risk_scores` (batch or one-by-one).

3. **Config**  
   - Allow `data_dir` and `model_path` to be overridden by env (e.g. `DADM_DATA_DIR`, `DADM_MODEL_PATH`) for containerized runs.

**Deliverables:** `agent/src/main.rs` (loop + uplink); `agent/src/uplink.rs` (new module); `agent/Cargo.toml` (add reqwest); config and README update.

---

## Phase 2 — Fusion ONNX export fix and training one-shot

1. **Federated server ONNX export**  
   - In `run_aggregation_and_publish()` and `bootstrap_version_zero()`, export the same wrapper as training: **ScoreWrapper(anomaly_score)** so the ONNX output is [1, 1] anomaly score, not reconstruction.  
   - Reuse the wrapper class from training or define it in federated (same signature as agent expects).

2. **Training one-command script**  
   - Add `training/run_all.py` or extend `run_pipeline.sh`: generate dummy data (if no data path), train, export ONNX, optionally quantize — so a single command produces `model.onnx` the agent can use.

**Deliverables:** `federated/server.py` (export with ScoreWrapper); `training/run_pipeline.sh` or `run_all.py` (single entry point).

---

## Phase 3 — Graph: subgraph export, batch ingest, startup

1. **Subgraph endpoint**  
   - `GET /api/v1/subgraph?node_id=did:xxx&hops=2&window_sec=3600` (or similar): run Cypher to get nodes and edges around node_id within hops and optional time window; return JSON `{ "nodes": [...], "edges": [...] }` for use by reasoning service.

2. **Batch ingest**  
   - `POST /api/v1/ingest/batch`: body with arrays `devices`, `events`, `risk_scores`; upsert all. Reduces round-trips when agent uplinks.

3. **Startup**  
   - On first request or in a `before_first_request` (or app init), call `ensure_indexes()`.  
   - Optionally use a single shared `Neo4jStore` (or connection pool) instead of creating a new store per request.

4. **Neo4j compatibility**  
   - Dashboard queries use `datetime()` and `duration()`; if targeting Neo4j 4.x, pass datetimes as parameters instead of Cypher `datetime()` and keep compatibility.

**Deliverables:** `graph/api.py` (subgraph, batch ingest, ensure_indexes, shared store or pool); `graph/neo4j_store.py` (subgraph query method).

---

## Phase 4 — Reasoning service

1. **Flask/FastAPI app**  
   - `POST /v1/reason`: body `{ "query": "...", "node_id": "did:xxx", "hops": 2 }`.  
   - Call graph API `GET /api/v1/subgraph?node_id=...&hops=...` to get context.  
   - Build prompt from template (system + user with structured context); call LLM (OpenAI-compatible or stub if no key).  
   - Parse response as JSON; validate against `reasoning/schemas/explanation_output.json`.  
   - Citation guardrail: ensure every `citations[]` id appears in subgraph nodes/edges; if not, return 422 or strip invalid steps.  
   - Append audit log entry (file or stdout) per `audit_log_entry.json`.

2. **Stub LLM**  
   - If no API key or `USE_STUB_LLM=true`, return a fixed JSON explanation with placeholder steps and citations from the subgraph (so the pipeline is testable without an LLM).

**Deliverables:** `reasoning/app.py` (or `reasoning/service/main.py`), `reasoning/prompts.py` (templates), `reasoning/guardrails.py` (citation check), `reasoning/requirements.txt`, `reasoning/README.md` update.

---

## Phase 5 — Mesh enrollment server (minimal)

1. **Flask app**  
   - `POST /v1/enroll`: accept token (static token from config/env for demo), CSR (PEM); return a self-signed or CA-signed cert + CA cert + config (bootstrap_peers, crl_url).  
   - `GET /v1/crl`: return empty or static CRL (signed).  
   - `POST /v1/rotate`: require TLS client cert; accept CSR; return new cert.  
   - In-memory or file-based cert store; optional use of `cryptography` to generate CA and sign CSRs.

**Deliverables:** `mesh/server.py` (or `mesh/enrollment_server.py`), `mesh/requirements.txt`, use existing `crypto_utils` or minimal crypto for CSR signing.

---

## Phase 6 — Docker Compose and runbook

1. **Compose stack**  
   - Services: `neo4j`, `fusion` (federated server), `graph` (graph API), `agent` (optional, with uplink to graph), `reasoning` (optional), `mesh` (optional).  
   - Env for agent: `DADM_UPLINK_ENABLED=true`, `DADM_UPLINK_ENDPOINT=http://graph:5001` (or fusion URL).  
   - Graph env: `NEO4J_URI=bolt://neo4j:7687`, etc.  
   - Fusion and graph ports exposed; agent uses graph as uplink to populate DSO.

2. **Runbook**  
   - `docs/RUNBOOK.md` or section in README: start order (Neo4j → fusion → graph → agent); how to run training and copy model into agent or fusion; how to trigger aggregate and pull model.

**Deliverables:** `docker-compose.yml`, `docs/RUNBOOK.md`, root README update (Run full stack).

---

## Phase 7 — Deploy and tests

1. **Ansible**  
   - Make “reboot for fips” handler conditional or remove automatic reboot; document manual reboot step.

2. **Integration test**  
   - Script or pytest: start Neo4j (or use testcontainers), start graph API, POST device + events + risk_scores, GET dashboard endpoints, optionally run propagation and clustering.  
   - Agent: unit test for uplink (mock HTTP) and daemon loop (run N cycles then stop).

**Deliverables:** Ansible handler fix; `tests/integration_graph.py` or similar; agent test for uplink.

---

## Execution order

1. Phase 2 (fusion ONNX fix) — quick win so agent and fusion models match.  
2. Phase 1 (agent daemon + uplink) — agent runs continuously and pushes to graph.  
3. Phase 3 (graph subgraph, batch, startup) — graph ready for reasoning and batch uplink.  
4. Phase 4 (reasoning service) — operational with stub LLM.  
5. Phase 5 (mesh enrollment) — minimal runnable server.  
6. Phase 6 (Docker Compose + runbook) — one-command stack.  
7. Phase 7 (deploy tweaks + integration tests) — polish.

---

## Document control

- **Created:** 2025-02-26  
- **Status:** Plan approved; implementation in progress.
