<p align="center">
  <img src="https://img.shields.io/badge/DADM-Aiximius-0f172a?style=for-the-badge&labelColor=0ea5e9&color=1e293b" alt="DADM Aiximius" />
</p>

<p align="center">
  <strong>Distributed AI Defense Mesh</strong> — Edge anomaly detection, federated learning, and defense graph correlation.
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
- [Documentation](#documentation)
- [Architecture at a glance](#architecture-at-a-glance)

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
│   ├── src/               # Collectors, features, model, storage, risk, logging
│   ├── benches/           # Performance benchmarks
│   └── README.md
├── training/              # Anomaly model training (Python)
│   ├── train.py           # Train autoencoder / Isolation Forest
│   ├── export_onnx.py     # Export to ONNX
│   ├── quantize.py        # Dynamic quantization
│   ├── drift.py           # Drift detection
│   ├── explain.py         # Feature importance / SHAP
│   └── README.md
├── federated/             # Secure federated learning (Python)
│   ├── client.py          # Encrypted gradient push (no raw logs)
│   ├── server.py          # Decrypt-only aggregation, versioning, rollback
│   ├── crypto_utils.py    # Hybrid encryption, signing
│   ├── compression.py    # Top-K + quantization
│   └── README.md
├── graph/                 # DSO graph engine (Python + Neo4j)
│   ├── schema.py          # Ontology: Device, Event, RiskScore, Cluster, etc.
│   ├── neo4j_store.py     # Graph read/write
│   ├── risk_propagation.py
│   ├── clustering.py     # Coordinated anomaly spike detection
│   ├── api.py             # REST API + dashboard queries
│   ├── examples/         # Cypher dashboard queries
│   └── README.md
├── mesh/                  # Zero-trust communication mesh (design + API spec)
│   ├── openapi.yaml      # Example secure APIs (enrollment, rotation, CRL, gossip, DTN)
│   └── README.md
└── docs/                  # Architecture and design
    ├── ARCHITECTURE.md    # System architecture, security, model lifecycle
    ├── EDGE-MODEL-DESIGN.md
    ├── FEDERATED-LEARNING.md
    ├── DSO-ONTOLOGY.md    # Defense Systems Ontology & graph
    ├── ZERO-TRUST-MESH.md # TLS, attestation, rotation, revocation, gossip, DTN
    └── architecture-diagram.mmd
```

---

## Quick start

### Edge agent (Rust)

```bash
cd agent
cargo build --release
./target/release/dadm-agent
```

Uses `config.json` if present; see [agent/README.md](agent/README.md). Requires an ONNX model (train via `training/`).

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
# GET /api/v1/dashboard/high_risk_devices, coordinated_spikes, surveillance_summary, event_volume
```

---

## Components

| Component | Role | Tech |
|-----------|------|------|
| **agent** | Edge endpoint: collect process/network/file/privilege events, extract features, run ONNX anomaly model, store encrypted, score risk. | Rust, ONNX Runtime |
| **training** | Train anomaly model (autoencoder / Isolation Forest); export ONNX; quantize; drift detection; explainability. | Python, PyTorch, ONNX |
| **federated** | Secure FL: clients send only encrypted gradient updates; server decrypts and aggregates; model versioning and rollback; air-gap export. | Python, Flask, cryptography |
| **graph** | Defense Systems Ontology: devices, events, risk scores, time windows, clusters. Risk propagation; unsupervised clustering for coordinated spikes; surveillance summary (non-intrusive); REST API. | Python, Neo4j, Flask |
| **mesh** | Zero-trust communication: TLS 1.3 mutual auth, hardware-backed keys, attestation, certificate rotation, CRL/revocation, encrypted gossip for anomaly signatures, delay-tolerant bundles. Design + OpenAPI spec. | Design, OpenAPI 3.0 |

---

## Documentation

| Doc | Description |
|-----|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture, data flows, model lifecycle, security, edge model, federated learning. |
| [EDGE-MODEL-DESIGN.md](docs/EDGE-MODEL-DESIGN.md) | Feature schema, model choice, training pipeline, ONNX, quantization, drift, explainability. |
| [FEDERATED-LEARNING.md](docs/FEDERATED-LEARNING.md) | Federated protocol, secure aggregation, compression, versioning, verification, failure recovery. |
| [DSO-ONTOLOGY.md](docs/DSO-ONTOLOGY.md) | Defense Systems Ontology schema, graph data model, risk propagation, clustering, API, dashboard queries. |
| [ZERO-TRUST-MESH.md](docs/ZERO-TRUST-MESH.md) | Zero-trust mesh: network architecture, auth flow, key lifecycle, enrollment, revocation, gossip, DTN; example secure APIs. |

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
