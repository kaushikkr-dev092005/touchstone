locals {
  tags = { project = "touchstone", financial_dispatch = "disabled" }
}
resource "oci_core_vcn" "touchstone" {
  compartment_id = var.compartment_ocid
  cidr_blocks    = ["10.77.0.0/16"]
  display_name   = "touchstone-vcn"
  dns_label      = "touchstone"
  freeform_tags  = local.tags
}
resource "oci_core_internet_gateway" "touchstone" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.touchstone.id
  enabled        = true
  display_name   = "touchstone-internet"
}
resource "oci_core_route_table" "touchstone" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.touchstone.id
  route_rules {
    network_entity_id = oci_core_internet_gateway.touchstone.id
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
  }
}
# Explicit empty list avoids inheriting an unrelated VCN's default SSH rules.
resource "oci_core_security_list" "closed" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.touchstone.id
  display_name   = "touchstone-nsg-only"
}
resource "oci_core_subnet" "touchstone" {
  compartment_id    = var.compartment_ocid
  vcn_id            = oci_core_vcn.touchstone.id
  cidr_block        = "10.77.1.0/24"
  route_table_id    = oci_core_route_table.touchstone.id
  security_list_ids = [oci_core_security_list.closed.id]
  display_name      = "touchstone-public"
  dns_label         = "web"
}
resource "oci_core_network_security_group" "touchstone" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.touchstone.id
  display_name   = "touchstone-web-ssh"
}
resource "oci_core_network_security_group_security_rule" "ingress" {
  for_each                  = { ssh = 22, http = 80, https = 443 }
  network_security_group_id = oci_core_network_security_group.touchstone.id
  direction                 = "INGRESS"
  protocol                  = "6"
  source                    = each.key == "ssh" ? var.admin_ipv4_cidr : "0.0.0.0/0"
  source_type               = "CIDR_BLOCK"
  description               = each.key == "ssh" ? "Owner IPv4 only; key authentication" : "Public web proxy only"
  tcp_options {
    destination_port_range {
      min = each.value
      max = each.value
    }
  }
}
resource "oci_core_network_security_group_security_rule" "web_egress" {
  for_each                  = { http = 80, https = 443 }
  network_security_group_id = oci_core_network_security_group.touchstone.id
  direction                 = "EGRESS"
  protocol                  = "6"
  destination               = "0.0.0.0/0"
  destination_type          = "CIDR_BLOCK"
  description               = "Signed package repositories, reviewed images, TLS and permitted read-only requests"
  tcp_options {
    destination_port_range {
      min = each.value
      max = each.value
    }
  }
}
resource "oci_core_network_security_group_security_rule" "resolver" {
  for_each                  = { dns_udp = { protocol = "17", port = 53 }, dns_tcp = { protocol = "6", port = 53 }, ntp = { protocol = "17", port = 123 } }
  network_security_group_id = oci_core_network_security_group.touchstone.id
  direction                 = "EGRESS"
  protocol                  = each.value.protocol
  destination               = "169.254.169.254/32"
  destination_type          = "CIDR_BLOCK"
  dynamic "udp_options" {
    for_each = each.value.protocol == "17" ? [1] : []
    content {
      destination_port_range {
        min = each.value.port
        max = each.value.port
      }
    }
  }
  dynamic "tcp_options" {
    for_each = each.value.protocol == "6" ? [1] : []
    content {
      destination_port_range {
        min = each.value.port
        max = each.value.port
      }
    }
  }
}
resource "oci_core_network_security_group_security_rule" "mtu" {
  network_security_group_id = oci_core_network_security_group.touchstone.id
  direction                 = "INGRESS"
  protocol                  = "1"
  source                    = "0.0.0.0/0"
  source_type               = "CIDR_BLOCK"
  icmp_options {
    type = 3
    code = 4
  }
}
resource "oci_core_instance" "touchstone" {
  compartment_id       = var.compartment_ocid
  availability_domain  = var.availability_domain
  display_name         = "touchstone-oracle"
  shape                = "VM.Standard.A1.Flex"
  preserve_boot_volume = true
  shape_config {
    ocpus         = 2
    memory_in_gbs = 12
  }
  source_details {
    source_type             = "image"
    source_id               = var.image_ocid
    boot_volume_size_in_gbs = 50
    boot_volume_vpus_per_gb = 10
  }
  instance_options {
    are_legacy_imds_endpoints_disabled = true
  }
  create_vnic_details {
    subnet_id        = oci_core_subnet.touchstone.id
    assign_public_ip = true
    nsg_ids          = [oci_core_network_security_group.touchstone.id]
  }
  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data           = base64encode(templatefile("${path.module}/bootstrap.sh.tftpl", { admin_ipv4_cidr = var.admin_ipv4_cidr }))
  }
  freeform_tags = local.tags
  lifecycle {
    prevent_destroy = true
  }
}
output "instance_id" {
  value     = oci_core_instance.touchstone.id
  sensitive = true
}
output "public_ip" {
  value     = oci_core_instance.touchstone.public_ip
  sensitive = true
}
