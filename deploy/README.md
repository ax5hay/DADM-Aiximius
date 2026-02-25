# Hardened Government Deployment — IaC

Example **Terraform** and **Ansible** for air-gapped, signed-image, audit-compliant DADM deployment. Use in conjunction with [GOVERNMENT-DEPLOYMENT.md](../docs/GOVERNMENT-DEPLOYMENT.md).

## Layout

| Path | Purpose |
|------|---------|
| **terraform/** | On-prem cluster: VMs (or node pool), network, optional Kubernetes bootstrap, private registry placeholder. State kept inside boundary. |
| **ansible/** | OS hardening, Secure Boot check, registry config, image verification, audit logging agent, offline model update. |
| **kubernetes/** | Example hardened Deployment (Fusion) with securityContext, digest pinning, and namespace Pod Security Standard. |

## Prerequisites

- Terraform 1.x; provider(s) for your on-prem or cloud (e.g. vSphere, Nutanix, or generic libvirt).
- Ansible 2.14+; inventory for cluster nodes.
- Signed container images and model packages on media (see supply chain workflow in the design doc).

## Air-gap usage

1. **Provision:** `cd terraform && terraform init -backend-config=... && terraform apply` (backend and vars point to in-boundary state and resources).
2. **Configure:** `ansible-playbook -i inventory ansible/site.yml` (or run playbooks in order per ansible/README).
3. **Import images:** Copy image tars + sigs to registry host; run import + verify playbook.
4. **Model update:** Copy signed model package to designated path; run model-verify-and-load playbook.

## Compliance

See [GOVERNMENT-DEPLOYMENT.md §3](../docs/GOVERNMENT-DEPLOYMENT.md#3-compliance-checklist-mapping) for mapping to NIST 800-53, FedRAMP, and FIPS-aligned crypto. Customize playbooks and Terraform to match agency baselines.
