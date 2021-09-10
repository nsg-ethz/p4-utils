variable "memory" {
  default = 4096
}

variable "cpus" {
  default = 4
}

variable "disk_size" {
  default = 25000
}

variable "vm_name" {
  default = "p4"
}

variable "username" {
  default = "p4"
}

variable "password" {
  default = "p4"
}

variable "iso_url" {
  default = "http://old-releases.ubuntu.com/releases/18.04.4/ubuntu-18.04.4-server-amd64.iso"
}

variable "iso_checksum" {
  default = "sha256:e2ecdace33c939527cbc9e8d23576381c493b071107207d2040af72595f8990b"
}

variable "target" {
  default = "sources.qemu.ubuntu18044_qemu"
}

packer {
  required_plugins {
    virtualbox = {
      version = ">= 0.0.1"
      source  = "github.com/hashicorp/virtualbox"
    }
    qemu = {
      version = ">= 0.0.1"
      source  = "github.com/hashicorp/qemu"
    }
  }
}

source "virtualbox-iso" "ubuntu18044_vb" {
  vm_name           = var.vm_name
  guest_os_type     = "Ubuntu_64"
  iso_url           = var.iso_url
  iso_checksum      = var.iso_checksum
  http_directory    = "http"
  cpus              = var.cpus
  memory            = var.memory
  disk_size         = var.disk_size
  ssh_username      = var.username
  ssh_password      = var.password
  ssh_timeout       = "1h"
  shutdown_command  = "echo ${var.password} | sudo -S shutdown -P now"
  format            = "ova"
  boot_wait         = "10s"
  boot_command      = [
    "<esc><wait>",
    "<esc><wait>",
    "<enter><wait>",
    "/install/vmlinuz<wait>",
    " initrd=/install/initrd.gz",
    " auto-install/enable=true",
    " debconf/priority=critical",
    " preseed/url=http://{{ .HTTPIP }}:{{ .HTTPPort }}/preseed.cfg<wait>",
    " -- <wait>",
    "<enter><wait>"
  ]
}

build {
  sources = [
    "sources.virtualbox-iso.ubuntu18044_vb"
  ]
  provisioner "shell" {
    inline = [
      "echo ${var.password} | sudo -S bash -c \"echo '${var.username} ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/99_advnet\"",
      "echo ${var.password} | sudo -S sudo chmod 440 /etc/sudoers.d/99_advnet",
      "sudo apt-get install -y git",
      "cd $HOME",
      "git clone https://github.com/nsg-ethz/p4-utils.git",
      "cd p4-utils",
      "cd install-tools",
      "./install-p4-dev.sh"
    ]
  }
}