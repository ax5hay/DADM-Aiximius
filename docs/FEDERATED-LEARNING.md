# Secure Federated Learning System for Anomaly Models

**Version:** 1.0  
**Constraints:** No raw logs from devices; decryption only at Aiximius servers; encrypted gradient updates only; asynchronous updates; intermittent connectivity; rollback on degradation; air-gapped sync via signed package.

---

## 1. Federated Protocol Design

### 1.1 Principles

| Principle | Implementation |
|-----------|----------------|
| **No raw logs** | Devices send only encrypted gradient updates (or encrypted weight deltas). No event payloads, cmdlines, or paths. |
| **Server-only decryption** | Updates encrypted with server’s public key (or hybrid: ephemeral key + server public key). Only Aiximius aggregation service holds the private key. |
| **Asynchronous** | Clients push updates when ready; server aggregates on a schedule or when a minimum cohort is reached. No synchronous rounds. |
| **Intermittent connectivity** | Clients buffer updates locally, retry with backoff; server accepts out-of-order contributions and tracks by round/version. |
| **Rollback** | Every global model is versioned and signed; if validation degrades, server publishes rollback to a previous version; edges verify signature and install. |
| **Air-gap** | Signed model package (model + metadata + signature) can be transferred offline and applied inside the boundary. |

### 1.2 Protocol Phases

```
[Client]                          [Aiximius Server]
   |                                       |
   |  (1) GET /config  (round, model version, server pubkey)
   | -------------------------------------->|
   |<--------------------------------------|  config + current_round, accepted_versions
   |                                       |
   |  (2) Local training on device (no raw logs leave device)
   |  (3) Compute gradients / weight delta
   |  (4) Compress + encrypt (server pubkey)
   |  (5) POST /updates  { encrypted_payload, client_id, round, signature }
   | -------------------------------------->|
   |                                       |  verify signature, decrypt (server only)
   |                                       |  store for round
   |<--------------------------------------|  202 Accepted (or 429 retry later)
   |                                       |
   |  (6) When cohort ready: aggregate, validate, sign new model
   |  (7) GET /model?version=N  (signed package)
   | -------------------------------------->|
   |<--------------------------------------|  signed model bundle
   |  (8) Verify signature, install, keep previous for rollback
```

- **Rounds:** Server assigns a round id per aggregation window. Clients submit updates tagged with the round they used (e.g. model version + round).
- **Idempotency:** Same client_id + round accepted once; duplicates ignored.
- **Async:** Steps (2)–(5) are independent of other clients; (6)–(7) can happen at any time after the server has enough contributions.

### 1.3 Message Types

| Message | Direction | Content |
|---------|-----------|--------|
| **Config** | Server → Client | `current_round`, `model_version`, `server_public_key`, `min_clients`, `grace_seconds` |
| **Update** | Client → Server | `client_id`, `round`, `encrypted_gradient_or_delta`, `signature`, `schema_version` |
| **Model package** | Server → Client | `version`, `model_blob`, `metadata`, `signature` (signed by Aiximius) |
| **Rollback** | Server → Client | Same as model package but `version` = previous known-good; clients replace current. |

---

## 2. Secure Aggregation Mechanism

### 2.1 Encryption of Updates

- **Client:** Encrypts gradient (or weight delta) with a **symmetric key** K, then encrypts K with the **server’s public key**. Sends `{ E_server(K), E_K(gradient) }`. No raw logs or plaintext gradients on the wire.
- **Server:** Decrypts K with server private key, then decrypts gradient. Decryption happens only on Aiximius servers; mesh relays never see plaintext.

### 2.2 Aggregation (After Decryption)

- **FedAvg:** For each parameter, server computes `new_param = (1/N) * sum(client_i_param)` or running average with momentum over asynchronous contributions.
- **By round:** Contributions with the same `round` and same `base_model_version` are aggregated; new global model is assigned `version = base_model_version + 1` and signed.
- **Optional:** Secure aggregation (e.g. additive secret sharing) so server only sees the sum; for simplicity, the sample implementation uses server-side decryption then FedAvg.

### 2.3 No Raw Logs

- Clients never send event payloads, logs, or raw features. Only model-related updates (gradients or parameter deltas) are sent, and only in encrypted form.

---

## 3. Gradient Compression Strategy

| Goal | Method |
|------|--------|
| **Bandwidth** | Reduce payload size for intermittent links. |
| **Privacy** | Smaller ciphertext; less to leak if ever intercepted. |

**Options:**

1. **Top-K / magnitude threshold:** Send only the largest K% of gradient entries (or above threshold); server treats missing as zero. Reconstruct sparse update.
2. **Quantization:** Quantize gradients to 8 or 4 bits; send scaling factor + integers. Server dequantizes before aggregation.
3. **Delta encoding:** Send difference from previous update; often sparser. Good with intermittent connectivity (client may send deltas relative to last accepted round).

**Recommended for anomaly model:** Top-K (e.g. 10–20%) + 16-bit quantization. Small model (e.g. 64→32→16→8→64) keeps update size low; compression ratio and accuracy tunable.

---

## 4. Model Versioning System

| Field | Description |
|-------|-------------|
| **version** | Monotonic integer (e.g. `model_version = 12`). Each aggregated model gets a new version. |
| **base_round** | Round id used for aggregation. |
| **created_at** | Timestamp (server). |
| **schema_version** | Feature schema version (e.g. `1.0`) for compatibility. |
| **rollback_of** | If this package is a rollback, points to the version that is being reverted to. |

**Registry (server):**

- Store each model artifact as immutable: `model_v{version}.onnx` + `model_v{version}.meta.json` + `model_v{version}.sig`.
- Clients request by version; server responds with signed package. For rollback, server publishes a package whose `version` is the previous known-good (or a dedicated `rollback_to_version` in metadata).

**Client:**

- Keeps at least the current active version and the previous one (for one-step rollback). On receiving a rollback directive or a new signed package, verifies signature, then installs and (if applicable) marks previous as rollback target.

---

## 5. Update Verification (Signature-Based)

### 5.1 Client → Server (Update)

- Client signs `H(client_id || round || encrypted_payload || schema_version)` with device private key. Server verifies with registered device public key; rejects invalid or replay (same client_id + round).

### 5.2 Server → Client (Model Package)

- Aiximius signs `H(version || model_blob || metadata)` with the **model signing key** (e.g. HSM). Client has the **model signing public key** (trust anchor). Before installing, client verifies signature; rejects if invalid.

### 5.3 Air-Gapped Package

- Signed package = `model.onnx` + `metadata.json` + `signature.bin`. Transfer via USB or internal network; verification uses the same public key. No online check required.

---

## 6. Failure Recovery Scenarios

| Scenario | Recovery |
|----------|----------|
| **Client offline during round** | Client keeps gradient/delta; when back online, sends for that round (if server still accepts) or for next round with current server model. Server can set `grace_seconds` per round. |
| **Server misses cohort** | Server extends round or starts new round; clients that already sent for old round can re-submit for new round with new model version. |
| **Update lost in transit** | Client retries with same (client_id, round); server idempotent (accepts once). |
| **Model degrades after deploy** | Server runs validation (e.g. holdout loss, drift metric). If degradation, server publishes **rollback** to previous version; clients pull signed rollback package and install. |
| **Compromised client** | Server can revoke client_id; contributions from that client ignored. Optional: attestation in update payload. |
| **Compromised server** | Private key material in HSM/TEE; rotation and revocation of old keys; clients get new signing public key via out-of-band or policy update. |
| **Air-gap: no network** | Sync via signed package: export from connected node or server, transfer media, import on air-gapped mesh; all nodes verify same signature. |

---

## 7. Sample Implementation

Located in **`federated/`** (PyTorch + Flask):

- **Client (`client.py`):** Load model (or fetch from server); compute gradients on local feature batch only (no raw logs); compress (top-K + 16-bit quantize); encrypt with server public key; sign payload; POST to `/updates` with retry and backoff. Tolerates intermittent connectivity.
- **Server (`server.py`):** `/config`, `/updates`, `/model`, `/aggregate`, `/rollback`, `/model/verify`. On `/updates`, verify signature, **decrypt only here**, decompress, accumulate by round; when cohort ready (or on `/aggregate`), FedAvg, apply to global model, version, sign, store. Rollback: set active version to previous; clients GET `/model` for signed package.
- **Secure channel:** TLS in production (reverse proxy); payload body encrypted (hybrid: E_server(K), E_K(gradient)). Signature over canonical JSON binds client and prevents tampering.
- **Crypto (`crypto_utils.py`):** Hybrid encrypt/decrypt (server RSA + AES-GCM); sign/verify for updates and model packages.
- **Compression (`compression.py`):** Top-K sparsification + 16-bit quantization; decompress on server after decrypt.
- **Versioning (`versioning.py`):** ModelMetadata, package paths, save/load signed package.
- **Air-gap:** `export_signed_package.py` exports model + metadata + signature to a directory; transfer; verify with `/model/verify` or standalone using server signing public key.

---

## Document Control

- **Created:** 2025-02-26  
- **Status:** Design approved  
- **Next:** Integrate into ARCHITECTURE.md; maintain sample in `federated/`.
