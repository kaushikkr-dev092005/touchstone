variable "oci_profile" {
  type    = string
  default = "TOUCHSTONE"
}
variable "tenancy_ocid" {
  type      = string
  sensitive = true
}
variable "compartment_ocid" {
  type      = string
  sensitive = true
}
variable "region" {
  type        = string
  description = "Privately verified tenancy home region; no default region substitution."
}
variable "availability_domain" {
  type      = string
  sensitive = true
}
variable "image_ocid" {
  type        = string
  description = "Reviewed official Ubuntu 24.04 ARM64 Always Free-eligible image."
}
variable "ssh_public_key" {
  type      = string
  sensitive = true
  validation {
    condition     = can(regex("^ssh-(ed25519|rsa) [A-Za-z0-9+/=]+", var.ssh_public_key))
    error_message = "An OpenSSH public key is required; never provide its private key."
  }
}
variable "admin_ipv4_cidr" {
  type      = string
  sensitive = true
  validation {
    condition     = can(cidrnetmask(var.admin_ipv4_cidr)) && endswith(var.admin_ipv4_cidr, "/32")
    error_message = "SSH requires the authorized operator's single IPv4 /32."
  }
}
variable "free_capacity_verified" {
  type        = bool
  default     = false
  description = "Set only after owner/account-wide eligibility and remaining quota review. Not financial authorization."
  validation {
    condition     = var.free_capacity_verified
    error_message = "BLOCKED_FREE_ELIGIBILITY: verify home region, billing, image and aggregate free usage first."
  }
}
