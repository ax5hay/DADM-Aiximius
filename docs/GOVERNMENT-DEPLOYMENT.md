# Hardened Deployment Configuration for Government Environments

**Purpose:** Air-gapped, signed, audit-compliant deployment of DADM in government or high-assurance on-prem environments.

**Requirements:** Air-gapped installation; signed container images; secure boot verification; audit-compliant logging; on-prem cluster orchestration; offline model update via signed package; FIPS-aligned crypto recommendations.

---

## Table of contents

| § | Topic |
|---|--------|
| 1 | [Deployment architecture](#1-deployment-architecture) |
| 2 | [Secure container configuration](#2-secure-container-configuration) |
| 3 | [Compliance checklist mapping](#3-compliance-checklist-mapping) |
| 4 | [Supply chain verification workflow](#4-supply-chain-verification-workflow) |
| 5 | [Infrastructure-as-code](#5-infrastructure-as-code-terraformansible) |

---

## 1. Deployment Architecture

### 1.1 Air-gapped boundary

```
                    ┌─────────────────────────────────────────────────────────────┐
                    │              AIR-GAPPED SECURE BOUNDARY (no internet)          │
                    │                                                              │
  [Media / USB]     │   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
  ───────────────►  │   │  Registry   │    │ Orchestrator │    │  Fusion /    │     │
  Signed images     │   │  (signed    │◄──►│ (K8s/OKD or │◄──►│  Graph /     │     │
  + model packages  │   │  only)      │    │  Nomad)     │    │  Mesh CA     │     │
                    │   └─────────────┘    └──────┬──────┘    └─────────────┘     │
                    │                             │                                │
                    │   ┌────────────────────────┼────────────────────────┐      │
                    │   │                        │                        │      │
                    │   ▼                        ▼                        ▼      │
                    │  [Agent]  [Agent]  [Fusion]  [Graph]  [Mesh relay]         │
                    │   (edge)  (edge)   (on-prem) (Neo4j)   (on-prem)           │
                    │                                                              │
                    └─────────────────────────────────────────────────────────────┘
```

- **Ingress:** Only via controlled media (USB/sanitized drive) or internal air-gap transfer. No outbound internet; no pull from public registries inside the boundary.
- **Registry:** Private registry inside the boundary. Only **signed** images are accepted (signature verification on push or on pull; see §2 and §4).
- **Orchestrator:** Kubernetes (e.g. OKD, K3s, or vendor K8s) or Nomad on-prem. All workload images from the internal registry.
- **Fusion / Graph / Mesh CA:** Run inside the boundary; model registry and signing keys on-prem; offline model update via signed package (§1.2).

### 1.2 Offline model update via signed package

- **Package:** Signed bundle (model blob + metadata + signature), produced in a connected or build environment and transferred on media (see federated `export_signed_package` and mesh design).
- **Ingress:** Operator copies package to a designated path (e.g. `/var/dadm/packages/`) on a node that has access to the model registry or fusion.
- **Verification:** Verification service (or fusion) validates signature against the **model signing public key** (trust anchor); rejects if invalid or tampered.
- **Deployment:** After verification, model is loaded into the model registry; orchestrator or agents pull/consume the new model per existing DADM model lifecycle (canary, rollback available). No network egress required.

### 1.3 Secure boot verification

- **Hosts:** All nodes that run DADM components (agents, fusion, graph, mesh) should boot with **UEFI Secure Boot** enabled. Only signed bootloader and OS kernel are loaded; measured boot (e.g. TPM PCRs) can be used for attestation.
- **Orchestrator nodes:** Control-plane and worker nodes: Secure Boot on; optional TPM-based attestation before joining the cluster.
- **Edge devices (government-managed):** Where supported (e.g. Windows, Linux, Android Enterprise), Secure Boot and verified boot are recommended; attestation can be used for mesh enrollment (see ZERO-TRUST-MESH).
- **Verification:** Documented process to verify Secure Boot status (e.g. `mokutil --sb-state`, Windows MSInfo, or orchestrator node conditions). Included in compliance checklist (§3).

### 1.4 Audit-compliant logging

- **Centralized log aggregation:** All DADM components emit structured logs (e.g. JSON). Logs are collected by a log aggregator (e.g. Fluent Bit, Vector, or SIEM agent) and forwarded to an **audit log store** (e.g. Elasticsearch, Splunk, or GovCloud-compliant service) inside the boundary.
- **Retention and immutability:** Audit logs are retained per policy (e.g. 1 year); append-only; access restricted; integrity protected (e.g. hashing or signing log streams).
- **Schema:** Log events include: timestamp, component, level, message, request_id, user/device id (where applicable), and no PII in clear text where policy forbids it. Align with [LLM-REASONING-LAYER](LLM-REASONING-LAYER.md) audit schema for reasoning; similar structured fields for fusion, mesh, graph, and agent.
- **No logging to internet:** All log sinks are internal; no external log forwarding from the air-gapped boundary.

---

## 2. Secure Container Configuration

### 2.1 Image signing and verification

- **Signing:** Images are signed with **Cosign** (Sigstore) or **Notary** (OCI Distribution) in the CI/build pipeline before export to media. Signing key is held in HSM or secure CI secret.
- **Registry policy:** Private registry (Harbor, Quay, or registry with verification) is configured to **reject** images that are not signed, or to only allow pulls of signed images (e.g. Cosign verification at pull time).
- **Orchestrator:** Kubernetes (or equivalent) is configured to **only allow** images from the internal registry; admission controller (e.g. Connaisseur, Sigstore Policy Controller, or OPA) verifies signature before pod admission. Unsigned or failed-verification images are rejected.

### 2.2 Container hardening

| Control | Recommendation |
|---------|----------------|
| **Non-root** | Run containers as non-root user (numeric UID); set `securityContext.runAsNonRoot: true`, `runAsUser`, `fsGroup` as needed. |
| **Read-only root FS** | `securityContext.readOnlyRootFilesystem: true` where the app supports it; use emptyDir or mounted volumes for writable paths. |
| **Drop capabilities** | Drop all capabilities; add only minimal if required: `securityContext.capabilities.drop: ["ALL"]`. |
| **No privilege escalation** | `securityContext.allowPrivilegeEscalation: false`. |
| **Seccomp / AppArmor** | Apply a restrictive seccomp profile (or AppArmor where available) per workload. |
| **Resource limits** | Set CPU/memory requests and limits to avoid resource exhaustion. |
| **No host namespace** | Do not use `hostNetwork`, `hostPID`, `hostIPC` unless strictly required and approved. |
| **Image digest pinning** | Reference images by digest (e.g. `registry/repo@sha256:...`) in deployments to pin to a specific build. |

### 2.3 Example Pod security (Kubernetes)

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  seccompProfile:
    type: RuntimeDefault
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop: ["ALL"]
```

- **Pod Security Standards:** Enforce **restricted** (or **baseline** with additional constraints) via namespace labels or admission controller.

---

## 3. Compliance Checklist Mapping

Mapping of deployment controls to common government and assurance frameworks (high-level; tailor to agency).

| Control area | NIST 800-53 (sample) | CISA / FedRAMP | DADM deployment action |
|--------------|----------------------|----------------|-------------------------|
| **Access control** | AC-2, AC-17 | Limit admin access; MFA for management | RBAC on orchestrator and registry; no internet access. |
| **Audit and accountability** | AU-2, AU-3, AU-6, AU-9 | Centralized, tamper-evident logs | Structured audit logging; retention; append-only store (§1.4). |
| **Configuration management** | CM-3, CM-5, CM-7 | Baseline configs; least functionality | IaC (Terraform/Ansible); hardened container and OS baseline. |
| **Contingency planning** | CP-2, CP-4 | Recovery procedures | Backup of registry, model registry, and config; restore runbooks. |
| **Identification and authentication** | IA-2, IA-5 | Strong auth; credential protection | Mesh TLS + certs; HSM/signing keys; no default credentials in images. |
| **Incident response** | IR-4, IR-6 | Incident handling and reporting | Logging and alerting; playbooks; no egress from boundary. |
| **System and communications protection** | SC-8, SC-12, SC-13, SC-28 | Encryption in transit/at rest; FIPS | FIPS-aligned crypto (§below); TLS 1.2+; encryption at rest for data stores. |
| **System and information integrity** | SI-3, SI-7, SI-12 | Malware protection; software integrity | Signed images only; Secure Boot; supply chain verification (§4). |

### 3.1 FIPS-aligned crypto recommendations

- **TLS:** Use TLS 1.2 or 1.3 with **FIPS-approved** cipher suites (e.g. TLS 1.3 with AES-GCM, or FIPS-mode OpenSSL). Disable weak ciphers and protocols.
- **Hashing:** SHA-256 or SHA-384 for signatures and integrity (e.g. image signing, model package signing).
- **Encryption at rest:** Use FIPS-validated modules (e.g. AES-256 in FIPS mode) for encrypting databases and sensitive stores (agent store, fusion, graph). Prefer OS or library FIPS mode (e.g. OpenSSL FIPS provider, BoringSSL FIPS).
- **Key storage:** Prefer HSM or TPM for CA and signing keys; key material in FIPS-validated storage where required.
- **Rust/Python:** In agent (Rust) and training/fusion (Python), use crypto libraries that support FIPS builds or link to FIPS-validated modules; document the chosen module and version for the compliance package.

---

## 4. Supply Chain Verification Workflow

### 4.1 Build and sign (outside or at boundary edge)

1. **Source:** Code from version control; tag or commit pinned for release.
2. **Build:** Build container images in a controlled CI environment; no unsigned images promoted.
3. **Sign:** Sign image with Cosign (or Notary) using a key from HSM or secure secret. Attach attestations (e.g. SLSA provenance) if required.
4. **Export:** Push signed images to a **staging registry** or export to **tar + sig files** for transfer. Export signing public key and (if applicable) attestation verification material with the media.

### 4.2 Transfer into air-gap

5. **Media preparation:** Copy signed image tars (and signatures) and/or model signed packages to sanitized media. Include verification script and public keys.
6. **Transfer:** Physically transfer media into the secure boundary. No network crossing.

### 4.3 Import and verify (inside boundary)

7. **Load images:** Import tars into the **private registry** inside the boundary (or load into a local registry that supports verification).
8. **Verify signature:** Before accepting an image, verify signature with the **supply chain public key** (Cosign verify, or equivalent). Reject if verification fails.
9. **Optional:** Verify attestations (provenance, vulnerability scan) if policy requires; fail if attestation check fails.
10. **Deploy:** Orchestrator pulls only from the internal registry; admission controller enforces signed images only (§2.1).

### 4.4 Model package supply chain

- **Build:** Model is built and signed in a trusted environment (see training and federated docs). Signing key is protected (HSM).
- **Package:** Signed package (model + metadata + signature) is written to media.
- **Import:** Inside boundary, run verification against the **model signing public key**; on success, load into model registry. No automatic execution of model code from untrusted source.

---

## 5. Infrastructure-as-Code (Terraform/Ansible)

- **Terraform:** Use for **provisioning** on-prem cluster resources (e.g. VMs, networks, firewall rules) and, where applicable, Kubernetes cluster (e.g. via provider or bootstrap). Terraform state stored inside the boundary (e.g. S3-compatible or local backend); no remote backend over internet.
- **Ansible:** Use for **configuration** of hosts and orchestrator: base OS hardening, Secure Boot verification check, FIPS mode, registry config, admission controller for image signing, audit log agent, and offline model update procedure (copy + verify script).

**Layout:**

- `deploy/terraform/` — Example Terraform for a small on-prem cluster (e.g. VMs + K8s bootstrap), private registry, and network segmentation.
- `deploy/ansible/` — Playbooks for: air-gap prerequisites, secure boot verification, registry import/verify, workload deployment, and offline model update steps.
- `deploy/kubernetes/` — Example hardened Deployment YAML (securityContext, image by digest, Pod Security Standard namespace).

**Usage (air-gap):**

1. Run Terraform (with state inside boundary) to create VMs and cluster.
2. Run Ansible playbooks to harden OS, configure registry, enable signature verification, and deploy DADM components from the internal registry.
3. Model updates: copy signed package to host; run Ansible play or script that verifies signature and updates model registry.

See `deploy/README.md` and per-directory READMEs for variables and execution order.

---

## Document Control

- **Created:** 2025-02-26  
- **Status:** Design approved  
- **Implementation:** `deploy/terraform/`, `deploy/ansible/` (example IaC); align with agency-specific hardening and compliance evidence.
