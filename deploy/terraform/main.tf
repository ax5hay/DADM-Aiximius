# DADM Government Deployment — On-prem cluster (example)
# Customize provider and resources for your environment (vSphere, Nutanix, libvirt, etc.).
# State must remain inside air-gapped boundary (local backend or in-boundary S3).

terraform {
  required_version = ">= 1.5"
  # Use a backend inside the secure boundary; no internet.
  # backend "s3" { ... }  # e.g. MinIO or in-boundary object store
  # backend "local" { path = "/secure/terraform.tfstate" }
}

# Example: generic variables for a small cluster
variable "cluster_name" {
  type    = string
  default = "dadm-gov"
}

variable "node_count" {
  type    = number
  default = 3
}

variable "registry_node_index" {
  type    = number
  default = 0
}

# Placeholder: replace with your provider (vsphere, nutanix, libvirt, etc.)
# provider "vsphere" { ... }
# resource "vsphere_virtual_machine" "node" { ... }

# Example output structure for Ansible inventory
output "cluster_nodes" {
  description = "List of node IPs or hostnames for Ansible"
  value       = [] # Populate from your VM/resources
}

output "registry_endpoint" {
  description = "Private registry endpoint (for image push/verify)"
  value       = "registry.${var.cluster_name}.local:5000"
}

output "kubeconfig_path" {
  description = "Path to kubeconfig if Kubernetes is provisioned"
  value       = "/etc/dadm/kubeconfig"
}
