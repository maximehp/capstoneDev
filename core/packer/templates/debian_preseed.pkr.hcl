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
variable "iso_file" { type = string }
variable "cpu" { type = number }
variable "ram_mb" { type = number }
variable "disk_gb" { type = number }
variable "bridge" { type = string }
variable "vlan" { type = number }
variable "ssh_username" { type = string }
variable "ssh_password" { type = string }
variable "ssh_timeout" { type = string }
variable "preseed_path" { type = string }
variable "bootstrap_script" { type = string }

source "proxmox-iso" "debian" {
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
    type     = "scsi"
    iso_file = var.iso_file
    unmount  = true
  }

  http_content = {
    "/preseed.cfg" = file(var.preseed_path)
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
    "auto url=http://{{ .HTTPIP }}:{{ .HTTPPort }}/preseed.cfg priority=critical ",
    "netcfg/choose_interface=auto ",
    "debian-installer=en_US locale=en_US.UTF-8 keyboard-configuration/xkb-keymap=us ---<enter>"
  ]

  communicator = "ssh"
  ssh_username = var.ssh_username
  ssh_password = var.ssh_password
  ssh_timeout  = var.ssh_timeout

  qemu_agent              = true
  cloud_init              = true
  cloud_init_storage_pool = var.storage_pool
  template_description    = "Built by Capstone (Debian preseed)"
}

build {
  name    = "capstone-debian-template"
  sources = ["source.proxmox-iso.debian"]

  provisioner "shell" {
    execute_command = "chmod +x {{ .Path }}; {{ .Vars }} sudo -E {{ .Path }}"
    script          = var.bootstrap_script
  }
}
