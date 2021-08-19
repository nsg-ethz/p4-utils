#!/bin/bash
packer init virtualbox.pkr.hcl
packer validate virtualbox.pkr.hcl
packer build virtualbox.pkr.hcl
