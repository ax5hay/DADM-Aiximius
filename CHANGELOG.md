# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Edge agent: daemon mode, uplink client to Graph API (device, events, risk scores), config via env (`DADM_*`).
- Federated server: ONNX export with `ScoreWrapper` (anomaly_score) for agent compatibility.
- Graph API: batch ingest (`POST /api/v1/ingest/batch`), subgraph endpoint (`GET /api/v1/subgraph`), `ensure_indexes` on startup.
- Reasoning service: Flask app (`POST /v1/reason`), prompts, citation guardrail, stub/OpenAI LLM, audit log.
- Mesh: enrollment server (Flask), CA and CSR signing (`POST /v1/enroll`, `GET /v1/crl`).
- Deploy: `verify_model_package.py` for signed model verification; Ansible playbooks use it.
- Docker Compose stack: Neo4j, Fusion, Graph, Reasoning, Mesh.
- Docs: IMPLEMENTATION-PLAN.md, RUNBOOK.md.
- CI: GitHub Actions (Rust, Python, Lint, Docker build, Deploy verify).
- Root: .gitignore, LICENSE (MIT), .editorconfig, CONTRIBUTING.md, SECURITY.md, Makefile, CHANGELOG.md; .github issue/PR templates, Dependabot.

### Changed

- Agent default: single-shot (`process_interval_secs: 0`); set >0 for daemon.
- Graph: device ingest parses optional `first_seen`/`last_seen`; index creation logs and skips on failure.

---

## [0.1.0] — Initial layout

- Agent (Rust): collectors, features, ONNX, storage, risk, logging.
- Training: train, export ONNX, quantize, drift, explain.
- Federated: server, client, crypto, compression, versioning.
- Graph: Neo4j store, propagation, clustering, Flask API.
- Mesh: OpenAPI spec. Reasoning: JSON schemas.
- Deploy: Terraform placeholder, Ansible playbooks (FIPS, audit, model update stubs).
