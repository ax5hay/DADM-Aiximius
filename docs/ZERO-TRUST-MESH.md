# Zero-Trust Communication Mesh for Distributed Defense Nodes

**Purpose:** Secure, delay-tolerant overlay for DADM nodes with TLS, hardware-backed keys where available, attestation, certificate rotation, and encrypted gossip for anomaly signatures.

**Requirements:** TLS between nodes; hardware-backed key storage where available; device attestation; certificate rotation; encrypted gossip-based anomaly signature propagation; delay-tolerant networking (DTN).

---

## 1. Network Architecture

### 1.1 Overlay Model

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                  MESH OVERLAY (DTN-aware)                  │
                    │  • Peer discovery: mDNS / DHT / bootstrap list (air-gap)  │
                    │  • Transport: TLS 1.3 (mutual auth) over TCP or QUIC      │
                    │  • Store-and-forward: bundles when peer unavailable       │
                    └─────────────────────────────────────────────────────────┘
                                         │
     ┌──────────┐    ┌──────────┐       │       ┌──────────┐    ┌──────────┐
     │  Node A  │◄──►│  Node B  │◄──────┼──────►│  Node C  │◄──►│  Node D  │
     │ (edge)   │    │ (relay)  │       │       │ (edge)   │    │ (edge)   │
     └────┬─────┘    └────┬─────┘       │       └────┬─────┘    └──────────┘
          │               │              │            │
          │    TLS 1.3 (mutual)         │            │
          │    Attestation + cert       │            │
          └────────────────────────────┴────────────┘
                    Optional: Fusion / CA
```

- **Nodes:** Edge agents or dedicated relays. Each node has a stable identity (node_id) bound to a key pair; private key in hardware (TPM/Secure Enclave/Keystore) where available.
- **Links:** TLS 1.3 with mutual authentication. Both sides present a certificate; chain validates to mesh root or fusion CA.
- **DTN:** When a peer is unreachable, messages (e.g. anomaly signatures, sync payloads) are stored as **bundles** and forwarded when connectivity is restored or via an intermediate relay. Bundle format: payload + metadata (destination, TTL, creation time); optional fragmentation for large payloads.
- **Gossip:** Anomaly signatures (hashes, risk indicators—no raw logs) are propagated via encrypted gossip: each node forwards signed announcements to a subset of peers; only nodes with valid certs and attestation (if enforced) accept and re-forward.

### 1.2 Components

| Component | Role |
|-----------|------|
| **Discovery** | Find peers (mDNS on LAN, DHT or bootstrap list for WAN/air-gap). |
| **TLS layer** | TLS 1.3; server and client certificates; ALPN e.g. `dadm-mesh/1`. |
| **Identity** | Per-node certificate (node_id in SAN or CN); private key from HSM/TPM/Keystore or software fallback. |
| **Attestation** | Optional: attestation payload (e.g. TPM quote, Android SafetyNet) sent at join or periodically; verifier validates against policy. |
| **Bundle store** | Local queue of outbound bundles (DTN); retry and TTL expiry. |
| **Gossip** | Receive signed anomaly-signature messages; validate; re-forward to fan-out peers; dedupe by message id. |

---

## 2. Authentication Flow

### 2.1 First Contact (TLS Handshake)

1. **Client (A) → Server (B):** ClientHello (ALPN `dadm-mesh/1`).
2. **B → A:** ServerHello, Certificate (B’s mesh cert), CertificateRequest (requesting client cert), ServerHelloDone.
3. **A → B:** Certificate (A’s mesh cert), CertificateVerify (signature over handshake), ClientKeyExchange.
4. **Both:** Finish. Application traffic is encrypted under the negotiated keys.

**Certificate validation:**

- A validates B’s cert: chain to mesh root CA (or fusion CA); check not revoked (CRL/OCSP or mesh CRL distribution).
- B validates A’s cert: same; optionally check attestation extension or separate attestation message after handshake.

### 2.2 Post-Handshake Attestation (Optional)

After TLS is up, A can send an **Attestation** message (over the secure channel):

- **Payload:** Platform attestation (e.g. TPM quote, SafetyNet attestation, or app attestation token).
- **Verifier (B or fusion):** Validates quote/token against policy (e.g. acceptable PCRs, nonce). If invalid, B can close the connection or demote A’s capabilities.
- **Binding:** Attestation can include a hash of A’s public key so that the attested identity is bound to the cert used in TLS.

### 2.3 Session Resumption

- Session tickets or resumption tickets (encrypted state containing peer identity and key material) allow quick reconnects without full cert exchange. Ticket lifetime and rotation policy align with certificate rotation (e.g. ticket lifetime &lt; cert validity).

---

## 3. Key Lifecycle Management

### 3.1 Key Types

| Key | Purpose | Storage | Rotation |
|-----|---------|---------|----------|
| **Identity (long-term)** | Signs node cert request; or is the key certified by mesh CA. | Hardware (TPM/Secure Enclave/Keystore) or encrypted software store. | Infrequent (e.g. annual or on compromise). |
| **Node certificate** | TLS client/server auth. | Same as identity or derived; cert stored with agent. | Rotation interval (e.g. 24h–7d) or on policy push. |
| **Session keys** | TLS session encryption. | In-memory; from TLS handshake. | Per session. |
| **Gossip signing** | Sign anomaly-signature messages. | Can be same as identity or ephemeral per epoch. | Align with cert or epoch. |

### 3.2 Certificate Rotation System

- **Trigger:** Time-based (e.g. new cert before expiry), or policy-based (fusion pushes “rotate now”).
- **Process:**  
  1. Node generates new key pair (in HSM if used).  
  2. Node creates CSR (or uses fusion/CA API); attestation optional.  
  3. CA (mesh root or fusion) issues new cert; node stores it.  
  4. Node starts using new cert for new TLS connections; old cert remains valid until its expiry (overlap window).  
  5. Node stops using old cert after expiry or after revocation is published.
- **Overlap:** CA issues certs with validity that overlaps the previous cert so that during rotation there is no connectivity gap.
- **Revocation:** See §5; rotated certs can be revoked if compromise is detected.

### 3.3 Hardware-Backed Storage (Where Available)

| Platform | Mechanism |
|----------|-----------|
| **Android** | Android Keystore (TEE or StrongBox); key attestation. |
| **iOS** | Secure Enclave; Secure Enclave attestation. |
| **Windows** | TPM 2.0 + CNG/DSS; TPM quote. |
| **macOS** | Secure Enclave (on supported hardware). |
| **Linux** | TPM 2.0 or soft HSM (e.g. PKCS#11); optional IMA. |

Agent uses a single abstraction (e.g. “identity key”) and platform layer resolves to the appropriate backend; fallback to encrypted file if no hardware.

---

## 4. Node Enrollment Process

### 4.1 Steps

1. **Bootstrap:** Node has a pre-provisioned **enrollment token** (or one-time code) and mesh CA/fusion endpoint (or bootstrap list for air-gap).
2. **Attestation (optional):** Node generates attestation payload (TPM quote, etc.) and sends it with enrollment request.
3. **Request:** Node generates identity key (hardware if available), builds CSR, sends to enrollment endpoint with token and attestation. Token is single-use or short-lived.
4. **Verification:** Enrollment service validates token; optionally validates attestation; checks policy (e.g. allow list, max nodes).
5. **Issuance:** CA issues node certificate (node_id in SAN); returns cert and optional mesh config (bootstrap peers, gossip params).
6. **Storage:** Node stores cert and private key in secure storage; marks itself enrolled.
7. **Join mesh:** Node uses new cert for TLS; discovers peers and participates in gossip/sync.

### 4.2 Air-Gap Enrollment

- Enrollment endpoint and CA run inside the boundary. Token and bootstrap list are provisioned via secure transfer (e.g. USB). Node connects only to internal enrollment API; no internet.

### 4.3 Renewal

- Same as rotation: node requests new cert (CSR + optional attestation) before expiry; CA issues; node switches to new cert with overlap period.

---

## 5. Revocation Protocol

### 5.1 Revocation Triggers

- Compromise or suspected compromise of a node or key.  
- Decommission.  
- Policy (e.g. device no longer in allow list).  
- Attestation failure (e.g. PCR mismatch).

### 5.2 Revocation Distribution

| Mechanism | Description |
|-----------|-------------|
| **CRL (Certificate Revocation List)** | CA publishes a signed list of revoked serial numbers (and optional node_ids). Nodes fetch CRL periodically or on connect; validate cert against CRL. |
| **OCSP (optional)** | Online check per cert; higher availability requirement. |
| **Mesh CRL gossip** | CRL or delta (revocation list) is propagated via the same gossip channel (signed by CA). Nodes update local revocation view and reject connections from revoked certs. |
| **Push** | Fusion or CA pushes “revoke node_id X” to connected nodes; nodes cache and enforce. |

### 5.3 Enforcement

- **TLS:** Before or during connection, verifier checks peer cert against current revocation state. If revoked, connection is rejected.
- **Gossip:** Messages signed by a revoked key are dropped and not re-forwarded.
- **State:** Revoked node_id is removed from local peer tables and not used for routing.

### 5.4 Timing

- Revocation takes effect as soon as a node receives the updated CRL or push. Until then, a revoked node might still be able to connect to nodes that have not yet seen the revocation; short CRL/gossip intervals reduce this window.

---

## 6. Encrypted Gossip-Based Anomaly Signature Propagation

### 6.1 Goal

- Propagate **anomaly signatures** (e.g. hash of risk event, indicator, or rule id)—not raw logs—so that other nodes can update local state (e.g. blocklist, detection rules). Traffic is encrypted (TLS) and messages are signed by the originator.

### 6.2 Message Format (Logical)

- **Message ID:** Unique (e.g. origin node_id + sequence or UUID).  
- **Origin:** node_id of source.  
- **Signature:** Over (message_id, origin, payload, timestamp).  
- **Payload:** Opaque to mesh (e.g. anomaly signature hash, type, minimal metadata).  
- **TTL / expiry:** So messages don’t propagate forever.

### 6.3 Propagation

- Node receives a message on a TLS link; verifies signature and revocation; dedupes by message_id.  
- If valid and new, re-forwards to a subset of peers (fan-out).  
- Encrypted by TLS; no additional application-layer encryption required for gossip payload if TLS is mandatory. Optional application-layer encryption for payload (e.g. only certain roles can read) can be added.

### 6.4 Delay Tolerance

- If peer is down, the node stores the message (or bundle) and forwards when the peer is back or via another path.  
- Bundles have TTL; expired bundles are discarded.  
- Ensures anomaly signatures eventually reach all connected nodes despite intermittent connectivity.

---

## 7. Example Secure API Definitions

Example APIs for enrollment, CA, and mesh control. Implementations live in repo under `mesh/api/` or similar.

### 7.1 Enrollment API

**POST /v1/enroll**

- **Request:**  
  - `token` (string): One-time enrollment token.  
  - `csr` (string): PEM or base64-encoded CSR.  
  - `attestation` (object, optional): `{ "type": "tpm_quote" | "safetynet" | ..., "payload": "<base64>" }`.  
  - `node_id` (string, optional): Requested node_id (or derived from attestation).
- **Response:**  
  - `certificate` (string): PEM-encoded leaf cert.  
  - `ca_cert` (string): Mesh root or issuing CA cert.  
  - `config` (object): `{ "bootstrap_peers": [...], "gossip_fanout": 3, "crl_url": "..." }`.
- **Auth:** None (token is the auth); or TLS with a provisional cert.  
- **Errors:** 400 invalid CSR/token, 403 attestation failed / policy, 429 rate limit.

### 7.2 Certificate Rotation API

**POST /v1/rotate**

- **Request:**  
  - `csr` (string): New public key.  
  - `attestation` (object, optional): Same as enroll.  
  - `current_cert_serial` (string): Serial of current cert (for audit).
- **Response:** `certificate` (string), `valid_not_before`, `valid_not_after`.
- **Auth:** TLS client cert (current mesh cert).  
- **Errors:** 401 no/invalid client cert, 403 attestation/policy failure.

### 7.3 CRL / Revocation API

**GET /v1/crl**

- **Response:** Signed CRL (DER or PEM) or delta CRL.  
- **Auth:** None (CRL is public) or TLS optional.  
- **Caching:** Clients use Cache-Control / ETag.

**POST /v1/revoke** (admin/internal)

- **Request:** `serial` (string), `reason` (optional), `node_id` (optional).  
- **Response:** 204 No Content.  
- **Auth:** Admin credential or internal service.

### 7.4 Mesh Health (Authenticated)

**GET /v1/mesh/peers**

- **Response:** List of peer node_ids and status (connected / last_seen).  
- **Auth:** TLS client cert (mesh cert).

**POST /v1/mesh/gossip**

- **Request:** Body = signed gossip message (message_id, origin, payload, timestamp, signature).  
- **Response:** 202 Accepted (message queued for propagation).  
- **Auth:** TLS client cert. Verifier checks signature and revocation.

### 7.5 Bundle (DTN) API

**POST /v1/bundles**

- **Request:** `destination` (node_id or “broadcast”), `ttl_sec` (number), `payload` (base64 or JSON).  
- **Response:** `bundle_id`, `expires_at`.  
- **Auth:** TLS client cert.

**GET /v1/bundles**

- **Response:** List of bundles destined for this node (or that this node should forward).  
- **Auth:** TLS client cert.

---

## Document Control

- **Created:** 2025-02-26  
- **Status:** Design approved  
- **Implementation:** Reference `mesh/` for example API specs and stubs; integrate with agent and fusion in later phases.
