# Government deployment — Terraform variables
# Override via .tfvars (keep .tfvars out of version control if they contain secrets)

variable "cluster_name" {
  type        = string
  description = "Cluster name used for resource naming"
}

variable "node_count" {
  type        = number
  description = "Number of worker/control nodes"
  default     = 3
}

variable "registry_node_index" {
  type        = number
  description = "Index of the node that will run the private registry"
  default     = 0
}

variable "enable_secure_boot" {
  type        = bool
  description = "Require UEFI Secure Boot for provisioned VMs (provider-dependent)"
  default     = true
}

variable "fips_mode" {
  type        = bool
  description = "Enable FIPS mode for OS (passed to Ansible)"
  default     = true
}

variable "audit_log_retention_days" {
  type        = number
  description = "Audit log retention in days"
  default     = 365
}
