<p align="center">
  <img src="https://img.shields.io/badge/DADM-Agent-0ea5e9?style=for-the-badge&labelColor=1e293b" alt="DADM Agent" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Rust-1.70%2B-dea584?style=flat-square&logo=rust&logoColor=white" alt="Rust 1.70+" />
  <img src="https://img.shields.io/badge/Platform-Android%20%7C%20iOS%20%7C%20Windows%20%7C%20macOS%20%7C%20Linux-64748b?style=flat-square" alt="Cross-platform" />
  <img src="https://img.shields.io/badge/Inference-ONNX-2d7dd2?style=flat-square" alt="ONNX" />
  <img src="https://img.shields.io/badge/Storage-Encrypted-10b981?style=flat-square" alt="Encrypted" />
</p>

<p align="center">
  <strong>Cross-platform defensive AI endpoint</strong> for the Distributed AI Defense Mesh.<br />
  Process · Network · File integrity · Privilege → behavioral features → anomaly score → encrypted store.
</p>

<p align="center">
  <em>Offline-first · Uplink optional (Aiximius-controlled)</em>
</p>

---

## Table of contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Build & run](#build--run)
- [Project structure](#project-structure)
- [Feature pipeline](#feature-pipeline)
- [Model (ONNX)](#model-onnx)
- [Storage & risk](#storage--risk)
- [Logging](#logging)
- [Benchmarks](#benchmarks)
- [Configuration](#configuration)

---

## Overview

| What | Description |
|------|-------------|
| **Role** | Edge agent: collect events, extract features, run local anomaly model, score risk, store encrypted. |
| **Data** | Raw sensitive data is not retained long-term on device; only aggregated features and scores. |
| **Connectivity** | Works fully offline; optional uplink to Aiximius is **server-controlled**, not user-controlled. |

---

## Requirements

- **Rust** 1.70+
- **ONNX model** (input `[1, N]` f32 → output score). If missing, inference is disabled (score 0.0).  
  Train and export with the [training pipeline](../training/) (Python).

---

## Build & run

```bash
# Build release
cd agent
cargo build --release
```

```bash
# Run (default config; optional config.json)
./target/release/dadm-agent
```

Optional: build without ONNX runtime (stub inference only):

```bash
cargo build --release --no-default-features
```

---

## Project structure

| Module | Purpose |
|--------|--------|
| `collectors` | Process, network, file integrity, privilege event collection |
| `features` | Sliding-window behavioral stats → fixed-dim feature vector |
| `model` | ONNX anomaly detection inference |
| `storage` | Encrypted SQLite (AES-256-GCM) for events and risk scores |
| `risk` | Threshold-based risk level (low / medium / high) |
| `logging` | Structured JSON logs (ndjson) |

```
agent/
├── src/
│   ├── main.rs          # Entry: collect → features → inference → risk → store
│   ├── lib.rs
│   ├── config.rs
│   ├── collectors/      # process, network, file, privilege
│   ├── features/        # behavioral stats, pipeline
│   ├── model/           # ONNX runtime
│   ├── storage/         # encrypted DB
│   ├── risk/            # scoring engine
│   └── logging/         # JSON format
├── benches/             # inference, pipeline, storage
├── tests/
├── config.sample.json
└── README.md
```

---

## Feature pipeline

1. **Events** from collectors (process, network, file, privilege).
2. **Sliding window** over the last N events.
3. **Behavioral stats**: counts per type, unique names/paths, byte totals, privilege success/fail.
4. **Vector**: normalized f32 vector of fixed dimension (e.g. 64), aligned with [training schema](../training/schema.py).

---

## Model (ONNX)

| Item | Spec |
|------|------|
| **Input** | `[1, feature_dim]` f32 (e.g. 64) |
| **Output** | Single f32 anomaly score in `[0, 1]` |
| **Missing model** | Agent runs with inference disabled (score 0.0) |

Train and export from the [training](../training/) package:

```bash
# From repo root
cd training && pip install -r requirements.txt
python train.py --data data.npy --out-dir out
python export_onnx.py --checkpoint out/model.pt --output out/model.onnx
# Copy out/model.onnx to agent dir or set model_path in config
```

---

## Storage & risk

- **Storage:** SQLite in `data_dir/store.db`. Event payloads **encrypted** (AES-256-GCM); key from device secret (production: Secure Enclave / Keystore / DPAPI).
- **Risk engine:** Raw score → configurable `medium_threshold` / `high_threshold` → **low** | **medium** | **high**.

---

## Logging

- **Format:** One JSON object per line (ndjson). Set `log.json: true` in config.
- **Level:** `RUST_LOG=info` (or config).
- **Fields:** `ts`, `level`, `target`, `message`, and optional `event_id`, `risk_score`, `risk_level`, `kind`, `error`.

---

## Benchmarks

Target: low-power devices. Tune `window_events` and collector intervals in config.

```bash
cargo bench
```

| Benchmark | Description |
|-----------|-------------|
| `inference_no_model_64d` | Inference path (no real model) |
| `inference_by_dim` | By feature dim (16 / 32 / 64 / 128) |
| `feature_extract_100_events` | Feature extraction over 100 events |
| `collectors_snapshot` | Full collector snapshot |
| `full_pipeline_snapshot_to_features` | End-to-end snapshot → features |
| `storage_insert_event` / `storage_get_event` | Encrypted store roundtrip |

---

## Configuration

| Option | Description |
|--------|-------------|
| `data_dir` | Directory for DB and model cache |
| `model_path` | Path to ONNX model file |
| `collectors.*` | Enable/disable collectors and intervals |
| `features.window_events` | Sliding window size |
| `features.feature_dim` | Model input dimension (e.g. 64) |
| `risk.high_threshold` / `medium_threshold` | Score thresholds (0–1) |
| `uplink.enabled` | **Set by Aiximius**; not user-controlled |
| `log.level` / `log.json` | Logging level and JSON output |

Example: copy `config.sample.json` to `config.json` and adjust paths/thresholds.
