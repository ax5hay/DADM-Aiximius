# Terraform — On-prem cluster

Example Terraform for provisioning the DADM government cluster. **Replace placeholder resources** with your provider (vSphere, Nutanix, libvirt, or cloud with private endpoint).

## Backend

- Use a **local** or **in-boundary** backend (e.g. `backend "local" { path = "/secure/dadm/terraform.tfstate" }` or in-boundary S3/MinIO).
- Do **not** use a remote backend that requires internet.

## Usage

```bash
terraform init
terraform plan -var-file=gov.tfvars
terraform apply -var-file=gov.tfvars
```

Export outputs (e.g. `cluster_nodes`, `registry_endpoint`) for Ansible inventory.

## FIPS / Secure Boot

- Set `enable_secure_boot = true` and `fips_mode = true` in tfvars where your provider supports them.
- Ansible will perform OS-level FIPS and Secure Boot verification.
