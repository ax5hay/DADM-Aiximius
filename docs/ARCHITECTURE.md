# Distributed AI Defense Mesh (DADM) — Production Architecture

**Version:** 1.0  
**Audience:** Senior distributed systems architects, security engineers  
**Constraints:** Consumer devices, offline-first, federated learning, single-device to government cluster, zero-trust, air-gapped capable.

---

## 1. System Architecture Diagram (Textual)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              DADM SYSTEM BOUNDARY                                         │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   ANDROID    │  │     iOS      │  │   WINDOWS    │  │    macOS     │  │    LINUX     │ │
│  │ Edge Agent   │  │ Edge Agent   │  │ Edge Agent   │  │ Edge Agent   │  │ Edge Agent   │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                 │                 │                 │                 │        │
│         └─────────────────┴────────┬────────┴─────────────────┴─────────────────┘        │
│                                    │                                                      │
│                          ┌─────────▼─────────┐     optional uplink                        │
│                          │    MESH SYNC      │◄──────────────────────────────┐            │
│                          │  (P2P / LAN /     │                               │            │
│                          │   WAN overlay)    │                               │            │
│                          └─────────┬─────────┘                               │            │
│                                    │                                         │            │
│         ┌──────────────────────────┼──────────────────────────┐             │            │
│         │                          │                          │             │            │
│  ┌──────▼──────┐            ┌──────▼──────┐            ┌──────▼──────┐  ┌───▼───────────┐│
│  │ Local Store │            │ Aggregator  │            │  Config /   │  │ Aiximius      ││
│  │ (encrypted) │            │ (in-mesh)   │            │  Policy     │  │ Fusion Server ││
│  └─────────────┘            └──────┬──────┘            └─────────────┘  │ (optional)    ││
│                                    │                                     └───────────────┘│
│                          ┌─────────▼─────────┐                                            │
│                          │  Model Registry   │  (signed, versioned, rollback-capable)     │
│                          └──────────────────┘                                            │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘

LAYERS:
  • Edge: per-device agents (inference + local training, attestation)
  • Mesh: overlay for sync, discovery, zero-trust channels
  • Fusion: optional central (Aiximius) for global aggregation, threat intel, model signing
  • Air-gap: mesh and fusion can be fully disconnected; fusion can run on-prem in cluster
```

**Key relationships:**
- **Edge ↔ Mesh:** All sync (gradients, model chunks, config) flows over the mesh overlay; no direct edge→fusion requirement.
- **Mesh ↔ Fusion:** Optional. When uplink exists, mesh gateways or designated nodes talk to Aiximius; otherwise mesh is self-contained.
- **Single device:** One edge agent + local store + no mesh peers = standalone mode.
- **Government cluster:** Many edge agents + on-prem mesh + on-prem fusion (air-gapped); same code paths, different topology and policy.

---

## 2. Component Breakdown

### 2.1 Edge Agent

| Responsibility | Description |
|----------------|-------------|
| **Inference** | Run local model(s) for detection/classification; low latency, offline. |
| **Local training** | Collect anonymized/local gradients or summary stats for federated rounds; optional differential privacy. |
| **Attestation** | Prove device/platform integrity (TPM/Secure Enclave/measured boot where available). |
| **Key material** | Device identity key, mesh session keys, optional fusion-bound credentials. |
| **Policy enforcement** | Apply config/policy from mesh or fusion; allow air-gapped policy bundles. |
| **Mesh client** | Join overlay, discover peers, participate in sync protocol; optional role as relay. |

**Deployment:** One process/service per device; shared core logic, platform-specific runners (Kotlin/JVM Android, Swift iOS, Rust or C++ core with platform bindings for desktop).

### 2.2 Mesh Sync

| Responsibility | Description |
|----------------|-------------|
| **Overlay** | Build and maintain P2P overlay (e.g. libp2p, custom over QUIC/TLS); support LAN-only, WAN, or mixed. |
| **Discovery** | Peer discovery (mDNS/LAN, DHT, or bootstrap list for air-gap). |
| **Zero-trust** | Mutual TLS or WireGuard-style tunnels; identity bound to attested device keys. |
| **Sync protocol** | Reliable, ordered (where needed) sync of: gradients, model deltas, config, heartbeat. Conflict resolution via vector clocks or last-write-wins with signed timestamps. |
| **Topology** | Scale from single node to large cluster; optional super-nodes or gateways for WAN or fusion uplink. |

**Modes:** Full mesh (small N), hierarchical or DHT-based (large N); same protocol, different routing. **Full design:** [ZERO-TRUST-MESH.md](ZERO-TRUST-MESH.md) (TLS, hardware-backed keys, attestation, certificate rotation, revocation, encrypted gossip, DTN); API spec `mesh/openapi.yaml`.

### 2.3 Fusion Server (Aiximius)

| Responsibility | Description |
|----------------|-------------|
| **Aggregation** | Receive encrypted/signed contributions from mesh; run federated aggregation (e.g. FedAvg, secure aggregation); produce new global model. |
| **Model registry** | Store and serve signed, versioned models; support rollback and canary. |
| **Threat intel** | Optional feed of signatures, rules, or labels into mesh. |
| **Policy & config** | Global or tenant-specific policy; push to mesh when connected. |
| **Identity & auth** | Issue or validate credentials for mesh nodes; optional PKI. |

**Deployment:** Can run in Aiximius cloud or on-prem; in air-gap, runs inside the secure boundary with no external network.

---

## 3. Data Flow Pipelines

### 3.1 Inference (Edge, offline-first)

```
[Sensor/Event] → [Edge Agent] → [Local Model] → [Decision/Alert]
                     ↑
               [Local Store: model, config]
```

- No server required. Model and config loaded from local encrypted store (updated via mesh or fusion when available).

### 3.2 Federated Learning — Contribution (Edge → Mesh / Fusion)

```
[Edge] Local training (feature vectors only; no raw logs)
    → gradients or weight deltas
    → compress (top-K, quantize)
    → encrypt (server public key; decrypt only at Aiximius)
    → sign with device key
    → send to Mesh / Fusion (async; retry on intermittent connectivity)
```

- **No raw logs:** Devices never send event payloads, cmdlines, or paths; only encrypted gradient/update payloads.
- **Decryption only at Aiximius:** Updates encrypted with server public key; only aggregation service holds the private key.
- See [Section 9](#9-secure-federated-learning-system) and [FEDERATED-LEARNING.md](FEDERATED-LEARNING.md).

### 3.3 Federated Learning — Aggregation (Mesh or Fusion)

```
[Mesh] Collect contributions from N edges
    → verify signatures & attestation
    → (optional) secure aggregation / decryption
    → aggregate (e.g. FedAvg)
    → produce new global model
    → sign model, bump version
    → publish to Model Registry
```

- Can run inside mesh (e.g. elected aggregator) or at fusion. Air-gap: aggregation stays on-prem.

### 3.4 Model Update & Rollback (Fusion/Mesh → Edge)

```
[Registry] signed model v2
    → mesh sync or direct fusion→edge
    → edge verifies signature & version
    → validate (e.g. sanity checks, canary)
    → atomic swap into Local Store
    → (optional) rollback token stored for quick revert
```

- Pipeline supports canary (subset of edges get v2 first) and rollback (revert to last known good version).

### 3.5 Config & Policy

```
[Fusion or Policy Node] policy/config bundle (signed)
    → mesh broadcast or targeted push
    → edge receives, verifies, applies
    → audit log locally
```

- Same flow works in air-gap with policy source inside the boundary.

---

## 4. Model Lifecycle

| Phase | Owner | Actions |
|-------|--------|--------|
| **Training** | Edge (local), Fusion (global) | Local: compute gradients on device; Global: run aggregation over contributions. |
| **Aggregation** | Mesh aggregator or Fusion | Combine updates; optional secure aggregation; output candidate model. |
| **Signing** | Fusion or on-prem signing service | Sign model artifact with registry key; record version and metadata. |
| **Publish** | Model Registry | Store (model blob + metadata + signature); expose to mesh/sync. |
| **Update** | Edge | Pull via mesh or fusion; verify; validate; atomic install; optional canary. |
| **Rollback** | Edge / Operator | Trigger revert to previous version (stored locally or re-fetched); re-verify and re-apply. |

**Versioning:** Semantic or monotonic (e.g. `model-20250226.12`). Each version is immutable and signed. Rollback = install previous version and mark as active.

**Canary:** Policy defines canary set (e.g. 5% of edges); they receive v2 first; if metrics OK, full rollout; else rollback and alert.

---

## 5. Security Model

### 5.1 Encryption

| Layer | Mechanism |
|-------|-----------|
| **At rest (edge)** | Local store encrypted with key derived from device secret (Secure Enclave/Keystore/DPAPI). |
| **In transit (mesh)** | TLS 1.3 or WireGuard; mutual auth with device identity. |
| **In transit (edge–fusion)** | TLS 1.3; client cert or token; optional E2E for contributions (e.g. fusion public key). |
| **Contributions** | Optional E2E: encrypt to fusion/aggregator so only aggregation layer can decrypt (e.g. threshold or hybrid). |

### 5.2 Attestation

- **Edge:** Where supported (Android Keystore, iOS Secure Enclave, TPM on Windows/Linux), attestation proves device integrity and binds keys. Attestation payload sent with critical operations (e.g. contribution, auth).
- **Fusion/aggregator:** Optional: run in TEE (e.g. confidential compute); attestation for code and model handling.

### 5.3 Signing

| Artifact | Signer | Verification |
|----------|--------|----------------|
| **Models** | Fusion or on-prem signing key (hardware-backed) | Edge and mesh nodes verify before install/forward. |
| **Config / policy** | Policy authority key | Edge verifies before apply. |
| **Contributions** | Device key | Aggregator/fusion verifies before aggregation. |
| **Mesh messages** | Per-session or per-device | Integrity and origin. |

**Trust anchor:** Root of trust for DADM (e.g. Aiximius root CA or on-prem root); device and fusion certs chain to it.

### 5.4 Zero-Trust in the Mesh

- No implicit trust by location; every connection authenticated and authorized.
- Identity = attested device key (or cert issued by fusion/on-prem CA).
- Authorization: policy defines which roles can contribute, aggregate, or pull models; enforced at aggregator and edge.

---

## 6. Tech Stack Suggestions

| Concern | Suggestion | Rationale |
|---------|------------|-----------|
| **Core logic (cross-platform)** | **Rust** | Performance, safety, single codebase for crypto and sync; easy FFI to Kotlin/Swift/C#. |
| **Edge UI / platform glue** | **Kotlin** (Android), **Swift** (iOS), **C#** or **Rust+TAO** (Windows), **Swift/AppKit** (macOS), **Rust+GTK** or **Qt** (Linux) | Native UX and store compliance. |
| **Mesh overlay** | **libp2p** (Rust/Go) or **QUIC** (e.g. quinn) + custom discovery | Mature P2P, TLS, NAT traversal; QUIC good for unreliable links. |
| **Federated learning** | **PyTorch** or **JAX** for server-side aggregation; **TFLite** or **ONNX** on edge for inference | Ecosystem and deployment; convert trained model to edge format. |
| **Model format (edge)** | **ONNX** or **TFLite** | Portable, optimized runtimes (ONNX Runtime, TFLite) on all platforms. |
| **Runtime (edge inference)** | **ONNX Runtime** / **TFLite Interpreter** / **CoreML** (iOS) | Cross-platform + native acceleration where needed. |
| **Fusion / aggregation** | **Rust** or **Go** for service; **Python** for research/aggregation scripts if needed | Throughput and safety; Python only where necessary. |
| **Storage (edge)** | **SQLite** (encrypted) or **Rust crate (e.g. sled)** with encryption layer | Simple, portable, offline-first. |
| **Crypto** | **ring** / **RustCrypto** (Rust); **BoringSSL** or platform APIs (mobile) | Consistency and FIPS where required. |

**Summary:** Rust core (mesh, crypto, sync, model load/verify); platform-native UI and lifecycle; ONNX or TFLite on edge; federated aggregation in Rust/Go/Python; optional Python for experimentation.

---

## 7. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| **Poisoning / malicious contributions** | Signed contributions; optional attestation; outlier detection and clipping in aggregation; secure aggregation to limit visibility of single contribution. |
| **Model theft or tampering** | Signing and verification; encrypted distribution; attestation of aggregator/fusion in sensitive deployments. |
| **Single device / small mesh** | Offline-first design; standalone mode with local model and config; no hard dependency on mesh or fusion. |
| **Scale (large N)** | Hierarchical or DHT-based mesh; sharded aggregation or multiple fusion nodes; rate limiting and backpressure. |
| **Air-gap and compliance** | Full stack runs on-prem; no default egress; policy and model sources inside boundary; documented air-gap deployment and update process. |
| **Key compromise (edge)** | Short-lived session keys; attestation to detect clone; revoke device at fusion and drop from mesh. |
| **Key compromise (fusion/signing)** | HSM/signing in TEE; key rotation and versioned trust; rollback and re-sign if needed. |
| **Availability of fusion** | Mesh and edge operate without fusion; aggregation can run in-mesh; fusion optional for global model and threat intel. |
| **Platform diversity** | Shared Rust core; thin platform adapters; clear API boundary for crypto and sync. |
| **Regulatory (data locality, privacy)** | No raw user data to fusion by design; optional DP; configurable retention and locality (e.g. EU-only aggregation). |

---

## 8. Edge-Optimized Anomaly Detection Model

**Constraints:** CPU-only, &lt;100MB memory, &lt;10ms inference per event; raw sensitive data stored server-side only; federated training support.

### 8.1 Feature Schema (Behavioral Events)

Features are derived from a sliding window of process, network, file integrity, and privilege events. Long-term raw data (cmdlines, paths, IPs) is **server-side only**; edge keeps only aggregated stats for inference.

| Index | Name | Normalization | Description |
|-------|------|---------------|-------------|
| 0–3 | process_count, network_count, file_count, privilege_count | /1000 | Event counts per type |
| 4–5 | unique_process_names, avg_cmdline_len | /500, /1000 | Process diversity and cmdline length |
| 6–7 | total_bytes_sent_norm, total_bytes_recv_norm | min(x/1e9,1) | Network volume |
| 8–9 | unique_file_paths, total_file_size_norm | /1000, min(x/1e9,1) | File activity |
| 10–11 | privilege_success, privilege_fail | /100 | Privilege escalation outcomes |

**Vector size:** 12 core features; padded to **64** for model input. Schema versioned; must match between training (`training/schema.py`) and edge agent.

### 8.2 Model Choice Comparison

| Criterion | Isolation Forest | Autoencoder | Tiny Transformer |
|-----------|------------------|-------------|-------------------|
| CPU inference | Very fast | Fast (small MLP) | Moderate |
| Memory | Low | Low–medium | Medium |
| &lt;10ms | Yes | Yes | Yes (tiny config) |
| Federated | Hard | Easy (FedAvg) | Easy |
| ONNX export | Via sklearn-onnx | Native | Native |
| Explainability | Path depth | Reconstruction per dim | Attention / importance |

**Recommendation:** **Autoencoder** as primary; Isolation Forest as baseline; Tiny Transformer optional for sequence-aware deployments.

### 8.3 Training Pipeline

- **Data:** Server-side only. Edge does not store raw events long-term; only features/scores for inference.
- **Stages:** Ingest → schema validation → train/val split → train (central or federated) → validate → export ONNX → optional quantize → sign & version.
- **Federated:** Clients compute local gradients/deltas on local feature batches; server aggregates (e.g. FedAvg). See `training/train.py` and `training/README.md`.

### 8.4 ONNX Export Configuration

- **Input:** `input`, shape `[1, 64]`, float32.
- **Output:** `output`, shape `[1, 1]`, float32 (anomaly score in [0,1]).
- **Opset:** 14. CPU-only ops; no dynamic shapes (batch 1).

### 8.5 Quantization Strategy

- **Dynamic quantization** (weights int8, activations float32) for smaller footprint and faster CPU inference. Optional step after export; validate score distribution and latency on target devices.

### 8.6 Drift Detection

- **Metric:** PSI or Wasserstein between current feature distribution and training reference.
- **Placement:** Server-side on aggregated stats; or edge sends periodic summary (no raw data) for server to compute. Threshold breach triggers retrain or canary. See `training/drift.py`.

### 8.7 Explainability

- **Reconstruction-based:** Per-feature reconstruction error (autoencoder); top-k features for high-risk events.
- **SHAP approximation:** KernelSHAP/SamplingExplainer server-side or offline; optional export of top-k indices for edge display. See `training/explain.py`.

**Detailed design:** [EDGE-MODEL-DESIGN.md](EDGE-MODEL-DESIGN.md). Production scripts: `training/`.

---

## 9. Secure Federated Learning System

**Constraints:** Devices never send raw logs; logs/updates decrypted only at Aiximius servers; only encrypted gradient updates; asynchronous updates; intermittent connectivity; rollback if model degrades; air-gapped sync via signed package.

### 9.1 Protocol Summary

| Phase | Description |
|-------|-------------|
| **Config** | Client GETs current round, model version, server public key, min_clients, grace_seconds. |
| **Update** | Client computes gradients on local features only → compress → encrypt (server pubkey) → sign → POST. Idempotent per (client_id, round). |
| **Aggregation** | Server decrypts (only here), FedAvg, applies to global model, validates, versions, signs, publishes to registry. |
| **Model / Rollback** | Client GETs signed model package by version; verifies signature; installs. Rollback = server publishes previous version; clients pull and install. |
| **Air-gap** | Signed package (model + metadata + signature) exported to file; transferred offline; verified and loaded inside boundary. |

### 9.2 Secure Aggregation

- **Encryption:** Hybrid: symmetric key K encrypts gradient blob; K encrypted with server RSA public key. Only Aiximius server can decrypt.
- **Signature:** Client signs update payload; server signs model packages. Verification before accept/install.
- **No raw data:** Only model-related updates (gradients/deltas) are sent; no event logs or raw features.

### 9.3 Gradient Compression

- Top-K sparsification + 16-bit quantization to reduce payload size for intermittent links. Server decompresses after decrypt.

### 9.4 Model Versioning and Rollback

- Monotonic version per aggregated model; immutable signed artifacts in registry. If validation degrades, server triggers rollback (publish previous version); clients verify and install.

### 9.5 Failure Recovery

| Scenario | Recovery |
|----------|----------|
| Client offline | Retry with backoff; server accepts async; round can be extended (grace_seconds). |
| Update lost | Re-send same (client_id, round); server idempotent. |
| Model degrades | Server publishes rollback; clients pull signed previous version. |
| Air-gap | Transfer signed package; verify with signing public key; load into local registry. |

**Detailed design:** [FEDERATED-LEARNING.md](FEDERATED-LEARNING.md). **Sample implementation:** `federated/` (PyTorch client, Flask server, crypto, compression, versioning, verification, export for air-gap).

---

## 10. Defense Systems Ontology (DSO) & Graph Engine

**Purpose:** Correlate anomalies across distributed nodes; risk propagation; cluster detection for coordinated anomaly spikes; non-intrusive surveillance tracking.

- **Ontology:** Device, Event, RiskScore, TimeWindow, Cluster, SurveillanceSubject; stable node IDs (`did:`, `evt:`, `clu:`, `win:`, `subj:`).
- **Graph (Neo4j):** Nodes and relationships (REPORTS, HAS_RISK_IN, MEMBER_OF, COMMUNICATES_WITH, TRACKED_AS, PROPAGATES_TO); indexes for query performance.
- **Risk propagation:** Propagate risk along COMMUNICATES_WITH and cluster membership; decay and max hops configurable.
- **Clustering:** Unsupervised grouping of devices with high risk in same window, connected by communication or cluster; outputs Cluster nodes and MEMBER_OF.
- **API:** Ingest devices/events/risk; trigger propagation and clustering; dashboard queries (high-risk devices, coordinated spikes, surveillance summary, event volume).
- **Surveillance (non-intrusive):** TRACKED_AS links Device to SurveillanceSubject; only aggregated counts and risk levels, no raw logs.

**Detailed design:** [DSO-ONTOLOGY.md](DSO-ONTOLOGY.md). **Implementation:** `graph/` (schema, Neo4j store, risk propagation, clustering, Flask API, example Cypher queries).

---

## 11. Zero-Trust Communication Mesh

**Purpose:** Secure, delay-tolerant overlay for node-to-node communication: TLS, hardware-backed keys, attestation, certificate rotation, encrypted gossip for anomaly signatures.

- **Network:** Overlay with peer discovery (mDNS/DHT/bootstrap); TLS 1.3 mutual auth; store-and-forward bundles for DTN when peers are unavailable.
- **Authentication:** Mutual TLS; both sides present mesh certificate; chain to mesh root or fusion CA; optional post-handshake attestation (TPM quote, SafetyNet, etc.).
- **Keys:** Identity key in TPM/Secure Enclave/Keystore where available; node certificate for TLS; rotation with overlap and revocation (CRL or mesh CRL gossip).
- **Enrollment:** Token + CSR + optional attestation → CA issues leaf cert and mesh config; air-gap via internal enrollment endpoint.
- **Revocation:** CRL (or delta) published and optionally gossiped; nodes reject connections and drop gossip from revoked certs.
- **Gossip:** Signed anomaly-signature messages (no raw logs); encrypted by TLS; dedupe and fan-out; DTN so messages propagate when connectivity returns.

**Detailed design:** [ZERO-TRUST-MESH.md](ZERO-TRUST-MESH.md). **Example APIs:** `mesh/openapi.yaml` (enrollment, rotation, CRL, gossip, bundles).

---

## 12. LLM-Based Reasoning Layer (Defensive Use)

**Purpose:** Use an LLM to reason over the **structured event graph** (DSO) and produce step-by-step explanations with citations and confidence—**without autonomous action**.

- **Constraints:** LLM cannot take autonomous action; operates only on the structured event graph; all outputs must cite graph nodes; step-by-step explanation and confidence score required.
- **Prompt design:** Versioned system prompt (analyst role, graph-only facts, mandatory citations, JSON-only output); user prompt = structured context (serialized subgraph) + natural-language query. No unstructured “context” other than the graph.
- **Context injection:** Subgraph selected by query (e.g. device, time range, cluster); serialized as node/edge JSON or triples; injected into prompt with a token limit; no raw logs.
- **Guardrails:** No tool use or action execution; post-response validation that every citation appears in the injected context; output schema enforced (explanation_steps, summary, confidence, confidence_justification); refusal for out-of-scope or action requests; low-confidence handling (e.g. flag for human review).
- **Audit:** Every request/response logged (prompt version, query, context node IDs, model, response type, confidence, citation verification result, latency); append-only; retention per policy.
- **Explanation output:** Structured JSON with steps (claim + citations array), summary, confidence in [0,1], confidence_justification. Citations use canonical graph IDs (did:, evt:, clu:, risk id).

**Detailed design:** [LLM-REASONING-LAYER.md](LLM-REASONING-LAYER.md). **Schemas:** `reasoning/schemas/` (explanation_output.json, audit_log_entry.json).

---

## 13. Hardened Government Deployment

**Purpose:** Air-gapped, signed, audit-compliant deployment for government or high-assurance on-prem environments.

- **Air-gap:** No internet inside boundary; ingress only via controlled media (signed images, signed model packages). Private registry and orchestrator (K8s/OKD or Nomad) on-prem.
- **Signed containers:** Images signed (e.g. Cosign/Notary) before transfer; registry and/or admission controller enforce signature verification; no unsigned images admitted.
- **Secure Boot:** UEFI Secure Boot enabled on hosts; measured boot/TPM optional for attestation. Verification step in deployment checklist.
- **Audit logging:** Centralized, structured, append-only; retention per policy; no egress. Schema aligned with compliance (e.g. NIST 800-53 AU-*).
- **Offline model update:** Signed model package on media → verify with model signing public key → load into model registry; no autonomous pull from internet.
- **FIPS-aligned crypto:** TLS with FIPS-approved ciphers; SHA-256/384 for signatures; encryption at rest with FIPS-validated modules where required; key storage in HSM/TPM.
- **Compliance mapping:** Checklist mapping to NIST 800-53, FedRAMP/CISA, and FIPS (see design doc §3).
- **Supply chain:** Build → sign → export to media → import inside boundary → verify signature → deploy. Model package same flow.
- **IaC:** Terraform for cluster provisioning (state in-boundary); Ansible for OS hardening, Secure Boot check, FIPS, audit config, and offline model update procedure.

**Detailed design:** [GOVERNMENT-DEPLOYMENT.md](GOVERNMENT-DEPLOYMENT.md). **IaC:** `deploy/terraform/`, `deploy/ansible/`.

---

## Document Control

- **Created:** 2025-02-26  
- **Updated:** 2025-02-26 (Section 13 Government Deployment)  
- **Status:** Draft for review  
- **Next:** Detailed protocol specs (mesh sync, federated rounds), API implementations, and deployment runbooks for single-device vs cluster vs air-gap.
