# DADM Secure Federated Learning — Sample Implementation

Sample implementation of the [secure federated learning system](../docs/FEDERATED-LEARNING.md) for anomaly models.

**Constraints:** No raw logs from devices; decryption only at Aiximius server; encrypted gradient updates only; asynchronous updates; intermittent connectivity; rollback on degradation; air-gapped sync via signed package.

## Quick start

```bash
cd federated
pip install -r requirements.txt
```

**Terminal 1 — Server (Aiximius):**
```bash
python server.py --port 5000
```

**Terminal 2 — Client (two clients to meet min_clients=2):**
```bash
python client.py --server http://127.0.0.1:5000 --client-id client-1
python client.py --server http://127.0.0.1:5000 --client-id client-2
```

**Trigger aggregation (after enough updates):**
```bash
curl -X POST http://127.0.0.1:5000/aggregate
```

**Pull signed model:**
```bash
curl "http://127.0.0.1:5000/model?version=1"
```

**Rollback (if model degrades):**
```bash
curl -X POST http://127.0.0.1:5000/rollback -H "Content-Type: application/json" -d '{"to_version": 0}'
```

## Components

| File | Purpose |
|------|--------|
| `protocol.py` | Config, Update, ModelPackage message types |
| `crypto_utils.py` | Hybrid encryption (server pubkey), sign/verify (client and server) |
| `compression.py` | Top-K + 16-bit quantization for gradients |
| `versioning.py` | Model version, metadata, package paths, rollback_of |
| `client.py` | Local training on features only, compress, encrypt, sign, POST with retry |
| `server.py` | /config, /updates (decrypt only here), /model, /aggregate, /rollback, /model/verify |
| `export_signed_package.py` | Export signed package for air-gap transfer |

## Secure channel

- **Transport:** TLS (use reverse proxy or `flask-talisman` in production).
- **Payload:** Updates are encrypted with server public key; only the server can decrypt. No raw logs or plaintext gradients on the wire.
- **Signature:** Client signs update payload; server signs model packages. Verification before install.

## Failure recovery

- **Client offline:** Retry with backoff (client.py does 3 attempts). Server accepts updates asynchronously; round can be extended.
- **Update lost:** Re-send same (client_id, round); server idempotent (duplicate ignored).
- **Model degrades:** POST /rollback with `to_version`; clients pull new active version (previous known-good).
- **Air-gap:** Export signed package via `export_signed_package.py`; transfer; verify with /model/verify or standalone script; load into local registry.

## Air-gapped sync

1. On connected node: `python export_signed_package.py --registry registry --version 1 --output signed_package`
2. Transfer `signed_package/` (model.onnx, metadata.json, signature.bin) to air-gapped network.
3. On air-gapped side: verify signature with server signing public key; install model into local registry or agent.
