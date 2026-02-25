# DADM Zero-Trust Communication Mesh

Design and example API definitions for the zero-trust communication mesh: TLS between nodes, hardware-backed keys where available, attestation, certificate rotation, encrypted gossip for anomaly signatures, and delay-tolerant networking.

**Design doc:** [ZERO-TRUST-MESH.md](../docs/ZERO-TRUST-MESH.md)

## Contents

| Item | Description |
|------|-------------|
| **openapi.yaml** | Example secure API definitions (OpenAPI 3.0) for enrollment, rotation, CRL, gossip, and DTN bundles. |
| **README.md** | This file. |

## API Overview

- **Enrollment:** `POST /v1/enroll` — token + CSR + optional attestation → certificate + mesh config.
- **Rotation:** `POST /v1/rotate` — TLS with current cert + CSR → new certificate.
- **Revocation:** `GET /v1/crl` — fetch CRL; `POST /v1/revoke` (admin) — revoke by serial.
- **Mesh:** `GET /v1/mesh/peers` — list peers (TLS); `POST /v1/mesh/gossip` — submit signed gossip message.
- **Bundles (DTN):** `POST /v1/bundles` — submit bundle; `GET /v1/bundles` — retrieve bundles for this node.

All mesh endpoints (except `/enroll` and `/crl`) require TLS 1.3 with client certificate (mutual auth).

## Use with codegen

```bash
# Example: generate client/server stubs (OpenAPI Generator)
docker run --rm -v "${PWD}:/local" openapitools/openapi-generator-cli generate \
  -i /local/openapi.yaml -g python-flask -o /local/server_stub
```
