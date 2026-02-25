<p align="center">
  <img src="https://img.shields.io/badge/DADM-Aiximius-0f172a?style=for-the-badge&labelColor=0ea5e9&color=1e293b" alt="DADM Aiximius" />
</p>

<p align="center">
  <strong>Distributed AI Defense Mesh</strong> — Edge anomaly detection, federated learning, and defense graph correlation.
</p>

<p align="center">
  <a href="https://github.com/Aiximius/DADM-Aiximius/actions"><img src="https://github.com/Aiximius/DADM-Aiximius/actions/workflows/rust.yml/badge.svg" alt="Rust CI" /></a>
  <a href="https://github.com/Aiximius/DADM-Aiximius/actions"><img src="https://github.com/Aiximius/DADM-Aiximius/actions/workflows/python.yml/badge.svg" alt="Python CI" /></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Rust-agent-dea584?style=flat-square&logo=rust&logoColor=white" alt="Rust" />
  <img src="https://img.shields.io/badge/Python-training%20%7C%20federated%20%7C%20graph-3776ab?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/ONNX-inference-2d7dd2?style=flat-square" alt="ONNX" />
  <img src="https://img.shields.io/badge/Neo4j-graph-008cc1?style=flat-square&logo=neo4j&logoColor=white" alt="Neo4j" />
  <img src="https://img.shields.io/badge/Offline--first-10b981?style=flat-square" alt="Offline-first" />
  <img src="https://img.shields.io/badge/Zero--trust-8b5cf6?style=flat-square" alt="Zero-trust" />
</p>

<p align="center">
  <em>Consumer to government · Encrypted · Federated · Air-gap capable</em>
</p>

---

## Table of contents

- [What is DADM?](#what-is-dadm)
- [Repository structure](#repository-structure)
- [Quick start](#quick-start)
- [Components](#components)
- [Testing and CI](#testing-and-ci)
- [Documentation](#documentation)
- [Architecture at a glance](#architecture-at-a-glance)

See also [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

---

## What is DADM?

**DADM (Distributed AI Defense Mesh)** is a production-grade system for defensive AI at the edge: anomaly detection on devices, optional federated learning with encrypted updates, and a **Defense Systems Ontology (DSO)** graph to correlate anomalies across nodes.

| Principle | Description |
|-----------|-------------|
| **Edge-first** | Agents run on Android, iOS, Windows, macOS, Linux; inference and local storage stay on device. |
| **Offline-first** | Full operation without connectivity; optional uplink controlled by Aiximius (server policy), not the user. |
| **No raw logs off device** | Only aggregated features and encrypted gradient updates leave the edge; decryption only at Aiximius servers. |
| **Zero-trust mesh** | Peer-to-peer sync with mutual auth; optional fusion server for aggregation and model registry. |
| **Air-gap ready** | Mesh and fusion can run entirely on-prem; model and policy updates via signed packages. |

---

## Repository structure

```
DADM-Aiximius/
├── agent/                 # Edge agent (Rust)
│   ├── src/               # Collectors, features, model, storage, risk, logging, uplink
│   ├── tests/             # Integration tests (config, pipeline, risk, storage, uplink)
│   ├── benches/           # Performance benchmarks
│   └── README.md
├── training/              # Anomaly model training (Python)
│   ├── train.py           # Train autoencoder / Isolation Forest
│   ├── export_onnx.py     # Export to ONNX (anomaly_score wrapper)
│   ├── quantize.py        # Dynamic quantization
│   ├── drift.py           # Drift detection
│   ├── explain.py         # Feature importance / SHAP
│   └── README.md
├── federated/             # Secure federated learning (Python)
│   ├── client.py          # Encrypted gradient push (no raw logs)
│   ├── server.py          # Decrypt-only aggregation, ONNX export (ScoreWrapper), versioning, rollback
│   ├── crypto_utils.py    # Hybrid encryption, signing
│   ├── compression.py     # Top-K + quantization
│   ├── export_signed_package.py  # Air-gap export
│   └── README.md
├── graph/                 # DSO graph engine (Python + Neo4j)
│   ├── schema.py          # Ontology: Device, Event, RiskScore, Cluster, etc.
│   ├── neo4j_store.py     # Graph read/write, subgraph query, ensure_indexes
│   ├── risk_propagation.py
│   ├── clustering.py      # Coordinated anomaly spike detection
│   ├── api.py             # REST API: ingest, batch ingest, subgraph, dashboard, propagate, clusters
│   ├── examples/          # Cypher dashboard queries
│   └── README.md
├── mesh/                  # Zero-trust mesh: enrollment server + OpenAPI spec
│   ├── openapi.yaml       # Secure APIs (enrollment, rotation, CRL, gossip, DTN)
│   ├── server.py          # Flask: POST /v1/enroll, GET /v1/crl, GET /v1/health
│   ├── ca_utils.py        # CA key/cert generation, CSR signing
│   ├── requirements.txt
│   └── README.md
├── reasoning/             # LLM reasoning layer (implemented)
│   ├── app.py             # Flask: POST /v1/reason (subgraph → prompt → LLM → guardrail → audit)
│   ├── prompts.py         # Versioned system/user prompts
│   ├── guardrails.py      # Citation validation (all citations in context)
│   ├── llm_client.py      # OpenAI-compatible or stub LLM
│   ├── audit.py           # Append-only audit log (schema: audit_log_entry.json)
│   ├── schemas/           # explanation_output.json, audit_log_entry.json
│   ├── requirements.txt
│   └── README.md
├── deploy/                # Government hardened deployment
│   ├── terraform/         # On-prem cluster provisioning (state in-boundary)
│   ├── ansible/           # OS hardening, Secure Boot, FIPS, audit, offline model update
│   │   ├── playbooks/     # site.yml, offline-model-update.yml
│   │   └── scripts/       # verify_model_package.py (signature verification with cryptography)
│   ├── docker/            # Dockerfiles for fusion, graph, reasoning, mesh
│   └── README.md
├── tests/                 # Unit tests (graph schema, reasoning guardrails, federated crypto, deploy verify)
│   ├── unit/
│   └── requirements.txt
├── docs/
│   ├── ARCHITECTURE.md
│   ├── IMPLEMENTATION-PLAN.md   # Phased plan: agent uplink, fusion ONNX, graph batch/subgraph, reasoning, mesh, compose
│   ├── RUNBOOK.md              # Full stack runbook: compose, agent uplink, training, reasoning, mesh
│   └── ... (other design docs)
├── .github/workflows/     # CI: Rust (fmt, clippy, test), Python (pytest), Lint (ruff, YAML), Docker build, Deploy verify
├── docker-compose.yml     # Neo4j, Fusion, Graph, Reasoning, Mesh
├── pyproject.toml         # Ruff config, pytest config
├── Makefile               # test, fmt, lint, docker-up/down
├── CHANGELOG.md           # Version history
├── CONTRIBUTING.md        # How to contribute
├── SECURITY.md            # Vulnerability reporting
└── README.md
```

---

## Quick start

### Run the full stack (Docker Compose)

From the repo root:

```bash
docker compose up -d
```

Starts **Neo4j**, **Fusion** (federated server), **Graph API**, **Reasoning** (stub LLM), and **Mesh** (enrollment). See [docs/RUNBOOK.md](docs/RUNBOOK.md) for ports, health checks, and running the agent with uplink to the graph.

### Edge agent (Rust)

```bash
cd agent
cargo build --release
./target/release/dadm-agent
```

- **Config:** `config.json` if present; overrides via env: `DADM_CONFIG_PATH`, `DADM_DATA_DIR`, `DADM_MODEL_PATH`, `DADM_UPLINK_ENABLED`, `DADM_UPLINK_ENDPOINT`, `DADM_DEVICE_ID`.
- **Modes:** Single shot (default: `process_interval_secs: 0`) or daemon loop when `process_interval_secs > 0` (graceful stop with Ctrl+C).
- **Uplink:** When `uplink.enabled` and `uplink.endpoint` are set, the agent registers the device and POSTs events and risk scores to the Graph API after each cycle.
- See [agent/README.md](agent/README.md). Requires an ONNX model (train via `training/` or pull from Fusion).

### Model training (Python)

```bash
cd training
pip install -r requirements.txt
python -c "
import numpy as np
from schema import CORE_FEATURE_DIM, normalize_core, to_model_input
x = np.random.rand(5000, CORE_FEATURE_DIM).astype(np.float32) * 100
np.save('data.npy', to_model_input(normalize_core(x)))
"
python train.py --data data.npy --out-dir out
python export_onnx.py --checkpoint out/model.pt --output out/model.onnx
```

### Federated learning (Python)

```bash
cd federated
pip install -r requirements.txt
# Terminal 1
python server.py --port 5000
# Terminal 2 (run twice with different client-id)
python client.py --server http://127.0.0.1:5000 --client-id client-1
curl -X POST http://127.0.0.1:5000/aggregate
```

### DSO graph engine (Python + Neo4j)

```bash
docker run -d -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:5
cd graph
pip install -r requirements.txt
export NEO4J_URI=bolt://localhost:7687 NEO4J_PASSWORD=password
python api.py
```

Endpoints: `POST /api/v1/devices`, `POST /api/v1/events`, `POST /api/v1/risk_scores`, `POST /api/v1/ingest/batch`, `GET /api/v1/subgraph?node_id=...&hops=2`, dashboard (`high_risk_devices`, `coordinated_spikes`, `surveillance_summary`, `event_volume`), `POST /api/v1/risk/propagate`, `POST /api/v1/clusters/run`. Indexes are created on first request.

### Reasoning layer (Python)

```bash
cd reasoning
pip install -r requirements.txt
export GRAPH_API_URL=http://localhost:5001
python app.py
# POST /v1/reason with {"query": "...", "node_id": "did:..."}  (USE_STUB_LLM=true or set OPENAI_API_KEY)
```

### Mesh enrollment (Python)

```bash
cd mesh
pip install -r requirements.txt
export MESH_ENROLL_TOKEN=secret
python server.py
# POST /v1/enroll (token + CSR), GET /v1/crl
```

---

## Components

| Component | Role | Tech |
|-----------|------|------|
| **agent** | Edge endpoint: collect process/network/file/privilege events, extract features, run ONNX anomaly model, store encrypted, score risk. Optional **uplink** to Graph API (device, events, risk scores). Daemon or single-shot. | Rust, ONNX Runtime, reqwest |
| **training** | Train anomaly model (autoencoder / Isolation Forest); export ONNX with anomaly_score wrapper; quantize; drift detection; explainability. | Python, PyTorch, ONNX |
| **federated** | Secure FL: clients send only encrypted gradient updates; server decrypts and aggregates; **ScoreWrapper** ONNX export for agent; versioning and rollback; air-gap export. | Python, Flask, cryptography |
| **graph** | DSO: devices, events, risk scores, time windows, clusters. **Batch ingest**, **subgraph** endpoint for reasoning; risk propagation; clustering; dashboard; indexes on startup. | Python, Neo4j, Flask |
| **mesh** | **Enrollment server:** POST /v1/enroll (token + CSR → cert + config), GET /v1/crl. CA and CSR signing. OpenAPI spec for full mesh (gossip, DTN). | Python, Flask, cryptography |
| **reasoning** | **Flask service:** POST /v1/reason — fetch subgraph from Graph API, build prompt, call LLM (OpenAI or stub), validate schema, citation guardrail, audit log. | Python, Flask, requests |
| **deploy** | Ansible: **verify_model_package.py** (signature verification with cryptography); Dockerfiles for Fusion, Graph, Reasoning, Mesh; Terraform + Ansible. | Terraform, Ansible, Docker |

---

## Testing and CI

- **Unit tests (Python):** `pytest tests/unit -v` from repo root (PYTHONPATH includes federated, graph, reasoning). Covers graph schema helpers, reasoning guardrails, federated crypto (sign/verify), and the deploy verify script.
- **Agent tests (Rust):** `cargo test` in `agent/` — config load, pipeline, risk thresholds, ONNX no-model, storage roundtrip, uplink client (new with endpoint vs disabled).
- **GitHub Actions:** On push/PR to main/master:
  - **Rust:** `cargo fmt --check`, `cargo clippy`, `cargo test` (agent).
  - **Python:** `pytest tests/unit` with deps from federated/graph/reasoning/mesh/tests.
  - **Lint:** Ruff (syntax), YAML check (docker-compose, mesh/openapi.yaml).
  - **Docker build:** Build Fusion, Graph, Reasoning, Mesh images (no push).
  - **Deploy verify:** Pytest for `verify_model_package.py` (valid/invalid signature, missing args).

---

## Documentation

| Doc | Description |
|-----|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture, data flows, model lifecycle, security, edge model, federated learning. |
| [EDGE-MODEL-DESIGN.md](docs/EDGE-MODEL-DESIGN.md) | Feature schema, model choice, training pipeline, ONNX, quantization, drift, explainability. |
| [FEDERATED-LEARNING.md](docs/FEDERATED-LEARNING.md) | Federated protocol, secure aggregation, compression, versioning, verification, failure recovery. |
| [DSO-ONTOLOGY.md](docs/DSO-ONTOLOGY.md) | Defense Systems Ontology schema, graph data model, risk propagation, clustering, API, dashboard queries. |
| [ZERO-TRUST-MESH.md](docs/ZERO-TRUST-MESH.md) | Zero-trust mesh: network architecture, auth flow, key lifecycle, enrollment, revocation, gossip, DTN; example secure APIs. |
| [LLM-REASONING-LAYER.md](docs/LLM-REASONING-LAYER.md) | LLM reasoning: prompt design, structured context injection, guardrails, audit logging schema, explanation outputs (citations, confidence). |
| [GOVERNMENT-DEPLOYMENT.md](docs/GOVERNMENT-DEPLOYMENT.md) | Hardened gov deployment: architecture, secure containers, compliance checklist, supply chain verification, Terraform/Ansible IaC. |
| [IMPLEMENTATION-PLAN.md](docs/IMPLEMENTATION-PLAN.md) | Phased implementation: agent daemon/uplink, fusion ONNX, graph batch/subgraph, reasoning service, mesh enrollment, Docker Compose. |
| [RUNBOOK.md](docs/RUNBOOK.md) | Run the full stack (Compose), agent with uplink, training→ONNX, reasoning (stub/LLM), mesh enrollment, troubleshooting. |

---

## Architecture at a glance

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   ANDROID   │     │     iOS     │     │  WINDOWS    │  ...
│ Edge Agent  │     │ Edge Agent  │     │ Edge Agent  │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
              ┌────────────▼────────────┐
              │   MESH SYNC (P2P)       │  optional uplink
              └────────────┬────────────┘
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Local Store │    │ Aggregator  │    │ Aiximius    │
│ (encrypted) │    │ (in-mesh)   │    │ Fusion      │
└─────────────┘    └──────┬──────┘    └──────┬──────┘
                         │                   │
                         ▼                   ▼
                  ┌─────────────┐    ┌─────────────┐
                  │ Model       │    │ DSO Graph   │
                  │ Registry    │    │ (Neo4j)    │
                  └─────────────┘    └─────────────┘
```

- **Edge:** Inference + local store; no raw logs sent.
- **Mesh:** Sync and optional aggregation; zero-trust.
- **Fusion:** Optional; encrypted aggregation, model registry, threat intel.
- **Graph:** Correlate anomalies across nodes; risk propagation; cluster detection; surveillance summary.

---

<p align="center">
  <strong>DADM Aiximius</strong> — Edge · Federated · Graph · Offline-first
</p>
