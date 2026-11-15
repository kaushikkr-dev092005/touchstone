# Copy to ignored tmp/oracle.tfvars; keep actual identifiers/private IPs out of Git.
oci_profile            = "TOUCHSTONE"
tenancy_ocid           = "REPLACE_PRIVATELY"
compartment_ocid       = "REPLACE_PRIVATELY"
region                 = "VERIFIED_HOME_REGION"
availability_domain    = "REPLACE_PRIVATELY"
image_ocid             = "VERIFIED_OFFICIAL_UBUNTU_24_04_ARM64_IMAGE"
ssh_public_key         = "REPLACE_WITH_PUBLIC_KEY_ONLY"
admin_ipv4_cidr        = "AUTHORIZED_PUBLIC_IPV4/32"
free_capacity_verified = false
