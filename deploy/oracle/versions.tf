terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "9.13.0"
    }
  }
}

provider "oci" {
  auth                = "SecurityToken"
  config_file_profile = var.oci_profile
  tenancy_ocid        = var.tenancy_ocid
  region              = var.region
}
