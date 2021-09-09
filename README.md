# P4-Utils

P4-Utils is an extension to *Mininet* that makes P4 networks easier to build, run and debug. P4-utils is strongly
inspired by [p4app](https://github.com/p4lang/p4app). Here we only provide a quick summary of the main information
about P4-Utils. **Check out the [online documentation](https://nsg-ethz.github.io/p4-utils/index.html)
for more details about P4-Utils installation and usage.**

## Installation

In order to work, P4-Utils needs different programs coming from different sources as prerequisites.
Since the installation process can be long and cumbersome, we provide different methods to make the
deployment easier for the users:

- [virtual machine](#virtual-machine) configured to work with P4-Utils,
- [manual installation](#manual-installation) using an installation script.

### Virtual Machine

P4-Utils can run in a virtual machine to keep its environment separated from the rest of the system.
Moreover, since P4-Utils is only available on Linux, other OS users can run it in a linux VM.

> Running P4-Utils in a completely separated environment can be beneficial: in this way, installation
> and execution errors, that may arise, will not affect the whole system. For this reason, we **recommend**
> using a virtual machine.

You can choose to download and use one of our 
[preconfigured VMs](https://nsg-ethz.github.io/p4-utils/installation.html#use-our-preconfigured-vm)
or to [build it by yourself](./vm).

### Manual Installation

If you have already installed all the [requirements](#requirements), you can simply
install P4-Utils using the following commands:

```bash
git clone https://github.com/nsg-ethz/p4-utils.git
cd p4-utils
sudo ./install.sh
```

> **Attention!**  
> The install script will use `pip -e` to install the project in editable mode, meaning that every time you update the files
> in this repository, either by pulling or doing local edits, the changes will automatically take place without the need of
> installing the package again.

If you want to uninstall run:

```bash
sudo ./uninstall.sh
```

This will remove all the scripts that were added to `/usr/bin` as well as uninstall the python package using `pip`.

#### Requirements

P4-Utils depends on the following programs in the given order:

1. [PI LIBRARY REPOSITORY](https://github.com/p4lang/PI) **is required only for topologies with
   P4Runtime switches**
2. [BEHAVIORAL MODEL (bmv2)](https://github.com/p4lang/behavioral-model)
3. [p4c](https://github.com/p4lang/p4c)
4. [Mininet](https://github.com/mininet/mininet)
5. [FRRouting](https://github.com/FRRouting/FRR) **is required 
   only for topologies with routers**

The manual installation process is quite long and cumbersome because of the
dependencies that are needed by P4-Utils. For this reason, we provide a Bash
script that automatically goes through every step.

> **Warning!**  
> The script has been tested with **Ubuntu 18.04.4** and the compiler
> **GCC 7.5**. Errors have been reported with newer versions.

In order to start the installation, you fist need to clone our repository:

```bash
git clone https://github.com/nsg-ethz/p4-utils
```

Then, you have to go to the installation folder::

```bash
cd p4-utils/install-tools
```

Finally, you can run the installation script::

```bash
sudo ./install-p4-dev.sh
```

This will install P4-Utils together with all its requirements.

### How does it work ?

P4-Utils creates virtual networks using mininet and extended nodes that run P4-enabled switches. To create hosts,
Mininet uses a bash process running in a network namespace, in order words, all the processes that run within the
network namespaces have an isolated network stack. Switches are software-based switches like Open vSwitch, Linux Bridge,
or BMV2 switches. Mininet uses virtual ethernet pairs, which live in the Linux kernel to connect the emulated hosts and switches.

For more information see:

 - [Mininet](http://mininet.org/)
 - [Linux Namespaces](https://blogs.igalia.com/dpino/2016/04/10/network-namespaces/)
 - [Virtual ethernet interfaces](http://man7.org/linux/man-pages/man4/veth.4.html)
 - [BMV2](https://github.com/p4lang/behavioral-model)
 - [p4runtime-shell](https://github.com/p4lang/p4runtime-shell)
 - [OVS](https://www.openvswitch.org/)
 - [LinuxBridge](https://cloudbuilder.in/blogs/2013/12/02/linux-bridge-virtual-networking/)

### Features

P4-Utils adds on top of minininet:

- A command-line launcher (`p4run`) to instantiate networks.
- A helper script (`mx`) to run processes in namespaces
- Custom `P4Host`, `P4Switch`, `P4RuntimeSwitch`, `FFRouter` nodes (based on the ones provided in the [`p4lang`](https://github.com/p4lang) repo)
- A very simple way of defining networks using JSON files (see `p4app_example.json` and [related documentation](https://nsg-ethz.github.io/p4-utils/usage.html#json)).
- A very intuitive programmatic way of defining networks using a Python API (see [related documentation](https://nsg-ethz.github.io/p4-utils/usage.html#python))
- Enhances mininet command-line interface: adding the ability of rebooting switches with updated P4 programs and configurations, without the need
 of restarting the entire network.
- Saves the topology and features in an object that can be loded and queried to extract meaningful information (see [related documentation](https://nsg-ethz.github.io/p4-utils/advanced_usage.html#topology-database)).
- Re-implementation of the `runtime_CLI` and `simple_switch_CLI` as Python objects to use in controller code.
- Re-implementation of the [p4runtime-shell](https://github.com/p4lang/p4runtime-shell) as Python objects to use in controller code.
