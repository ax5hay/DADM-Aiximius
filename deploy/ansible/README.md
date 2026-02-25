# Ansible — Government deployment configuration

Playbooks for hardened DADM deployment: OS hardening, Secure Boot verification, FIPS, audit logging, registry behavior, and **offline model update** (verify signed package and load).

## Playbooks

| Playbook | Purpose |
|----------|---------|
| **site.yml** | Full site: FIPS mode (grub), Secure Boot check, audit log directory and rsyslog/logrotate. |
| **offline-model-update.yml** | Verify signed model package and copy to model registry path; trigger reload. |

## Inventory

Define groups, e.g.:

- `all` — all nodes
- `registry` — node(s) running private registry
- `fusion` — node(s) running fusion / model registry

Use Terraform outputs to build inventory or a dynamic inventory script inside the boundary.

## Variables

- `dadm_fips_mode`: true to enable FIPS (grub) on RHEL/CentOS.
- `dadm_audit_log_retention_days`: 365 default.
- `dadm_package_dir`: `/var/dadm/packages` for model package drop.
- `dadm_model_signing_pubkey`: path to model signing public key.
- `model_package_path`: override path to signed package for offline-model-update.yml.

## Secure Boot

- `site.yml` runs `mokutil --sb-state` where available and records result. Use this for compliance evidence; fail or warn if Secure Boot is disabled per policy.

## Air-gap

- Run Ansible from a control node **inside** the boundary. No Ansible Galaxy or internet; copy roles/collections on media if needed.
