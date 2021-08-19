#!/bin/bash
packer init qemu.pkr.hcl
packer validate qemu.pkr.hcl
packer build qemu.pkr.hcl
