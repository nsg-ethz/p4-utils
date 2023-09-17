# Installation tools

The manual installation process is quite long and cumbersome because of the
dependencies that are needed by P4-Utils. For this reason, we provide a
[Bash script](https://github.com/nsg-ethz/p4-utils/blob/master/install-tools/install-p4-dev.sh)
that automatically goes through every step.

> **Warning!**  
> The script has been tested with **Ubuntu 20.04.6** and **Ubuntu 22.04.3**. 
> To install for **Ubuntu 18.04** refer to [this older script](./old_installs/install-p4-dev.sh).

With the following installation methods, you will download and install *Mininet*
and the P4-Tools suite (P4-Utils, P4-Learning and their dependencies) in your 
user's home directory.

## One-Step Automated Install

To get started quickly and conveniently, you may want to install the P4-Tools suite 
using the following command:

```bash
curl -sSL https://raw.githubusercontent.com/nsg-ethz/p4-utils/master/install-tools/install-p4-dev.sh | bash
```

## Alternative Installation Method

The main drawback of piping to `bash` is that you cannot review the code
that is going to run on your system. Therefore, we provide this alternative
methods that allows you to inspect the intallation script:

```bash
wget -O install-p4-dev.sh https://raw.githubusercontent.com/nsg-ethz/p4-utils/master/install-tools/install-p4-dev.sh
bash install-p4-dev.sh
```
