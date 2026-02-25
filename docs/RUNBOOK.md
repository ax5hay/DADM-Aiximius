# DADM Runbook — Run the Full Stack

## Quick start (Docker Compose)

From the repo root:

```bash
docker compose up -d
```

Services:

| Service   | Port | Purpose                    |
|-----------|------|----------------------------|
| Neo4j     | 7474 (HTTP), 7687 (bolt) | Graph DB                    |
| Fusion    | 5000 | Federated learning server  |
| Graph API | 5001 | DSO graph ingest & queries |
| Reasoning | 5002 | LLM reasoning (stub OK)    |
| Mesh      | 5003 | Enrollment & CRL           |

Health checks:

- Graph: `curl http://localhost:5001/api/v1/health`
- Fusion: `curl http://localhost:5000/config`
- Reasoning: `curl http://localhost:5002/v1/health`
- Mesh: `curl http://localhost:5003/v1/health`

## Running the agent with uplink

1. Start the stack (so Graph API is up).
2. Build and run the agent with uplink enabled:

   ```bash
   cd agent && cargo build --release
   DADM_UPLINK_ENABLED=true \
   DADM_UPLINK_ENDPOINT=http://localhost:5001 \
   DADM_DEVICE_ID=my-device-01 \
   ./target/release/dadm-agent
   ```

   For a single shot (no daemon loop), set in `config.json`: `"process_interval_secs": 0`.

3. For daemon mode (continuous collection and uplink), set `process_interval_secs` to a positive value (e.g. 300) in config or leave default after changing it.

## Order of operations

1. Start **Neo4j** first (Compose does this via `depends_on`).
2. Start **Fusion** and **Graph** (Graph needs Neo4j).
3. Start **Reasoning** (needs Graph for subgraph).
4. Run **Agent** on a host or container, with `DADM_UPLINK_ENDPOINT` pointing at Graph (e.g. `http://<graph-host>:5001`).

## Training a model and using it

1. From repo root, with Python env that has `training/` deps:

   ```bash
   cd training && python train.py --config config.yaml --output-dir out && \
   python export_onnx.py --checkpoint out/model.pt --output model.onnx
   ```

2. Use `model.onnx` as the agent’s model (e.g. `DADM_MODEL_PATH=/path/to/model.onnx`) or place it where the agent’s config points.

3. Fusion bootstrap creates a signed v0 model at first `/model` request; clients can pull from `GET /model` and verify with `/model/verify`.

## Reasoning layer

- Default: stub LLM (no API key). Set `USE_STUB_LLM=false` and `OPENAI_API_KEY` (or `LLM_API_KEY`) and optionally `OPENAI_BASE_URL`, `LLM_MODEL` to use a real LLM.
- POST ` /v1/reason` with body `{ "query": "Why is device X high risk?", "node_id": "did:X", "hops": 2 }`. Response is JSON explanation with steps and citations; audit log is written to stdout or `DADM_REASONING_AUDIT_LOG` file.

## Mesh enrollment

- Set `MESH_ENROLL_TOKEN` on the server (Compose: `change-me-in-production`).
- POST ` /v1/enroll` with `{ "token": "<token>", "csr": "<PEM or base64>" }` to get certificate and config (bootstrap_peers, crl_url).
- GET ` /v1/crl` for revocation list (minimal server returns empty list).

## Troubleshooting

- **Graph dashboard empty:** Ensure agent (or another client) has sent events and risk scores to `POST /api/v1/events` and `POST /api/v1/risk_scores` (or use batch `POST /api/v1/ingest/batch`).
- **Fusion model download fails:** Ensure `registry` volume is writable; bootstrap creates v0 on first `/model` request.
- **Neo4j connection refused:** Wait for Neo4j to finish startup (Compose healthcheck); then restart Graph service if needed.
