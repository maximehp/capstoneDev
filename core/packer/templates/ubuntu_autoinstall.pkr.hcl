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
variable "ssh_username" { type = string }
variable "ssh_password" { type = string }
variable "ssh_timeout" { type = string }
variable "user_data_path" { type = string }
variable "meta_data_path" { type = string }
variable "bootstrap_script" { type = string }

source "proxmox-iso" "ubuntu" {
  proxmox_url = var.proxmox_url
  username    = var.proxmox_username
  token       = var.proxmox_token
  node        = var.proxmox_node

  insecure_skip_tls_verify = var.proxmox_insecure_skip_tls_verify

  vm_id   = var.template_vmid
  vm_name = var.template_name

  memory = var.ram_mb
  cores  = var.cpu

  boot_iso {
    type             = "scsi"
    iso_url          = var.iso_url
    iso_checksum     = var.iso_checksum
    iso_storage_pool = var.iso_storage_pool
    unmount          = true
  }

  additional_iso_files {
    type     = "ide"
    cd_files = [var.user_data_path, var.meta_data_path]
    cd_label = "cidata"
    unmount  = true
  }

  network_adapters {
    bridge   = var.bridge
    model    = "virtio"
    vlan_tag = var.vlan
  }

  disks {
    storage_pool = var.storage_pool
    disk_size    = "${var.disk_gb}G"
    type         = "scsi"
  }

  boot_wait = "5s"
  boot_command = [
    "<esc><wait>",
    "e<wait>",
    "<down><down><down><end>",
    " autoinstall ds=nocloud;s=/cidata/ ---<f10>"
  ]

  communicator = "ssh"
  ssh_username = var.ssh_username
  ssh_password = var.ssh_password
  ssh_timeout  = var.ssh_timeout

  qemu_agent              = true
  cloud_init              = true
  cloud_init_storage_pool = var.storage_pool
  template_description    = "Built by Capstone (Ubuntu autoinstall)"
}

build {
  name    = "capstone-ubuntu-template"
  sources = ["source.proxmox-iso.ubuntu"]

  provisioner "shell" {
    execute_command = "chmod +x {{ .Path }}; {{ .Vars }} sudo -E {{ .Path }}"
    script          = var.bootstrap_script
  }
}
