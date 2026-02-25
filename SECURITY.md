# Security policy

## Supported versions

We provide security updates for the current default branch (`main` or `master`). Older branches are not officially supported.

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

- **Email:** Report sensitive security issues privately. If you have a contact for the maintainers, use it. Otherwise, you can open a **private** [GitHub Security Advisory](https://github.com/Aiximius/DADM-Aiximius/security/advisories/new) so only repository maintainers see the report.
- **What to include:** Description of the issue, steps to reproduce, impact (e.g. authentication bypass, key exposure), and any suggested fix or mitigation.
- **Response:** We will acknowledge the report and aim to respond within a reasonable time. We may ask for clarification. We will coordinate with you on disclosure (e.g. after a fix is released).

## Security-related design

- **Agent:** No raw logs leave the device by default; uplink is optional and server-controlled. Local storage is encrypted; keys should be device-bound (e.g. Secure Enclave / Keystore) in production.
- **Federated:** Decryption of client updates happens only on the server; model packages are signed. Verify signatures before loading models (see [deploy/ansible/scripts/verify_model_package.py](deploy/ansible/scripts/verify_model_package.py)).
- **Mesh:** Enrollment uses tokens and CSR; TLS and certificate lifecycle are described in [docs/ZERO-TRUST-MESH.md](docs/ZERO-TRUST-MESH.md).
- **Deployment:** See [docs/GOVERNMENT-DEPLOYMENT.md](docs/GOVERNMENT-DEPLOYMENT.md) for hardened deployment and supply-chain verification.

Thank you for helping keep DADM and its users safe.
