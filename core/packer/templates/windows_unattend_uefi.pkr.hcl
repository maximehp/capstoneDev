packer {
  required_plugins {
    proxmox = {
      source  = "github.com/hashicorp/proxmox"
      version = ">= 1.1.0"
    }
  }
}

variable "proxmox_url" { type = string }
variable "proxmox_username" { type = string }
variable "proxmox_token" { type = string }
variable "proxmox_insecure_skip_tls_verify" { type = bool }
variable "proxmox_node" { type = string }
variable "storage_pool" { type = string }
variable "iso_storage_pool" { type = string }
variable "template_name" { type = string }
variable "template_vmid" { type = number }
variable "iso_url" { type = string }
variable "iso_checksum" { type = string }
variable "cpu" { type = number }
variable "ram_mb" { type = number }
variable "disk_gb" { type = number }
variable "bridge" { type = string }
variable "vlan" { type = number }
variable "autounattend_path" { type = string }
variable "windows_virtio_iso_url" { type = string }
variable "winrm_username" { type = string }
variable "winrm_password" { type = string }
variable "winrm_port" { type = number }
variable "winrm_use_ssl" { type = bool }
variable "winrm_timeout" { type = string }
variable "bootstrap_script" { type = string }

source "proxmox-iso" "windows" {
  proxmox_url = var.proxmox_url
  username    = var.proxmox_username
  token       = var.proxmox_token
  node        = var.proxmox_node

  insecure_skip_tls_verify = var.proxmox_insecure_skip_tls_verify

  vm_id   = var.template_vmid
  vm_name = var.template_name
  bios    = "ovmf"
  machine = "q35"

  efi_config {
    efi_storage_pool = var.storage_pool
    pre_enrolled_keys = true
    efi_type = "4m"
  }

  tpm_config {
    storage_pool = var.storage_pool
    version      = "v2.0"
  }

  memory = var.ram_mb
  cores  = var.cpu

  boot_iso {
    type             = "sata"
    iso_url          = var.iso_url
    iso_checksum     = var.iso_checksum
    iso_storage_pool = var.iso_storage_pool
    unmount          = true
  }

  additional_iso_files {
    type             = "sata"
    iso_url          = var.windows_virtio_iso_url
    iso_checksum     = "none"
    iso_storage_pool = var.iso_storage_pool
    unmount          = true
  }

  additional_iso_files {
    type             = "ide"
    cd_files         = [var.autounattend_path]
    cd_label         = "AUTOUNATTEND"
    iso_storage_pool = var.iso_storage_pool
    unmount          = true
  }

  network_adapters {
    bridge   = var.bridge
    model    = "e1000"
    vlan_tag = var.vlan
  }

  disks {
    storage_pool = var.storage_pool
    disk_size    = "${var.disk_gb}G"
    type         = "sata"
  }

  communicator   = "winrm"
  winrm_username = var.winrm_username
  winrm_password = var.winrm_password
  winrm_port     = var.winrm_port
  winrm_use_ssl  = var.winrm_use_ssl
  winrm_insecure = true
  winrm_timeout  = var.winrm_timeout

  qemu_agent           = true
  template_description = "Built by Capstone (Windows UEFI TPM)"
}

build {
  name    = "capstone-windows-uefi-template"
  sources = ["source.proxmox-iso.windows"]

  provisioner "powershell" {
    script = var.bootstrap_script
  }
}
