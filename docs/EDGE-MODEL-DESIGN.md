# Edge-Optimized Anomaly Detection Model — Design

**Version:** 1.0  
**Constraints:** CPU-only, &lt;100MB memory, &lt;10ms inference per event, server-side raw data, federated training support.

---

## 1. Feature Schema for Behavioral Events

Features are derived from a sliding window of **process**, **network**, **file integrity**, and **privilege** events. Raw sensitive data (full cmdlines, paths, IPs) is **not** stored long-term on the edge; only aggregated stats are used for inference. Long-term raw storage is server-sided.

| Index | Name | Type | Normalization | Description |
|-------|------|------|---------------|-------------|
| 0 | `process_count` | count | / 1000 | Process events in window |
| 1 | `network_count` | count | / 1000 | Network flow events in window |
| 2 | `file_count` | count | / 1000 | File integrity events in window |
| 3 | `privilege_count` | count | / 1000 | Privilege escalation events in window |
| 4 | `unique_process_names` | count | / 500 | Distinct process names |
| 5 | `avg_cmdline_len` | float | / 1000 | Mean cmdline length |
| 6 | `total_bytes_sent_norm` | float | min(x/1e9, 1) | Bytes sent (capped) |
| 7 | `total_bytes_recv_norm` | float | min(x/1e9, 1) | Bytes received (capped) |
| 8 | `unique_file_paths` | count | / 1000 | Distinct file paths touched |
| 9 | `total_file_size_norm` | float | min(x/1e9, 1) | Total file size hashed (capped) |
| 10 | `privilege_success` | count | / 100 | Successful privilege escalations |
| 11 | `privilege_fail` | count | / 100 | Failed privilege escalations |

**Vector size:** 12 core features; padded to **64** for model input (reserved for future expansion). Schema is versioned and must match between training and edge agent.

---

## 2. Model Choice Comparison

| Criterion | Isolation Forest | Autoencoder | Tiny Transformer |
|-----------|------------------|-------------|-------------------|
| **CPU inference** | Very fast, trivial | Fast (small MLP) | Moderate (attention) |
| **Memory** | Low (trees) | Low–medium | Medium (params + cache) |
| **&lt;10ms** | Yes | Yes (small net) | Yes (tiny config) |
| **Federated** | Hard (tree structure) | Easy (FedAvg on weights) | Easy (FedAvg) |
| **ONNX export** | Sklearn → ONNX | Native PyTorch → ONNX | Native → ONNX |
| **Interpretability** | Path length / depth | Reconstruction per dim | Attention / feature importance |
| **Drift** | Retrain trees | Reconstruct error dist | Embedding / loss dist |

**Recommendation:** **Autoencoder** as primary: best balance of federated training, ONNX export, &lt;10ms CPU inference with a small MLP, and per-feature reconstruction for explainability. Isolation Forest as a fast baseline; Tiny Transformer optional for sequence-aware deployments where latency budget allows.

---

## 3. Training Pipeline

- **Data:** Server-side only. Edge sends only aggregated feature vectors or gradients (no raw events long-term on device).
- **Stages:** Ingest → schema validation → train/val split → train (central or federated) → validate → export ONNX → optional quantize → sign & version.
- **Federated:** Clients compute local gradients or model deltas on local feature batches; server aggregates (e.g. FedAvg). Only **encrypted** gradient updates are exchanged; no raw logs. Decryption only at Aiximius servers. See [FEDERATED-LEARNING.md](FEDERATED-LEARNING.md) and sample in `federated/`.
- **Output:** ONNX model (input `[1, 64]` f32, output `[1, 1]` f32 anomaly score), metadata (schema version, thresholds), and optional drift/explainability artifacts.

---

## 4. ONNX Export Configuration

- **Input:** name `input`, shape `[1, 64]`, type float32.
- **Output:** name `output`, shape `[1, 1]`, type float32 (anomaly score in [0, 1]).
- **Opset:** 14 for broad runtime support.
- **Optimization:** Constant folding, redundant node removal; no GPU-specific ops (CPU-only).
- **Dynamic shapes:** Not required; fixed batch size 1 for edge.

---

## 5. Model Quantization Strategy

- **Target:** Reduce memory and speed up CPU inference.
- **Options:** (1) **Dynamic quantization** (weights int8, activations float32) — minimal accuracy impact, good CPU gain. (2) **Static QAT** for smaller models if needed later.
- **Choice:** Start with FP32 export; add dynamic quantization (ONNX Runtime) in the pipeline for a second artifact `model_quantized.onnx`. Validate score distribution and &lt;10ms on target devices before rollout.

---

## 6. Drift Detection Mechanism

- **Input:** Stream of feature vectors (or their summaries) seen at inference time; reference distribution from training (e.g. mean/cov or histogram).
- **Metric:** PSI (Population Stability Index) or Wasserstein distance on marginal distributions per feature; or Mahalanobis distance in latent/reconstruction space for autoencoder.
- **Placement:** Server-side on aggregated stats; or lightweight edge component that sends periodic summary stats (no raw data) for server to compute drift. If drift &gt; threshold, trigger retrain or canary new model.

---

## 7. Explainability Method

- **Feature importance:** For autoencoder, use **reconstruction error per feature** (mask or ablate one feature at a time; difference from full reconstruction).
- **SHAP approximation:** Use **KernelSHAP** or **SamplingExplainer** on a small sample of points with the ONNX model (server-side or offline). Export per-event feature attributions for high-risk cases. LIME-style linear surrogate is an alternative for &lt;10ms interpretability requests.
- **Edge:** Optionally expose top-k contributing feature indices from a lightweight rule (e.g. top reconstruction errors) without full SHAP on device.

---

## Document Control

- **Created:** 2025-02-26  
- **Status:** Design approved  
- **Next:** Integrate into ARCHITECTURE.md; maintain training scripts in `training/`.
