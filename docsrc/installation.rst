Installation
============

In order to work, P4-Utils needs different programs coming from different sources as prerequisites.
Since the installation process can be long and cumbersome, we provide different methods to make the
deployment easier for the users:

- __ #virtual-machine

  `virtual machine`__ configured to work with P4-Utils,
- __ #manual-installation

  `manual installation`__ using an installation script.

__ #virtual-machine

.. Note::
    Running P4-Utils in a completely separated environment can be beneficial: in this way, installation
    and execution errors, that may arise, will not affect the whole system. For this reason, we **recommend**
    using a `virtual machine`__.

Virtual Machine
---------------

.. _VirtualBox: https://www.virtualbox.org/

.. _QEMU: https://www.qemu.org/

P4-Utils can run in a virtual machine to keep its environment separated from the rest of the system.
Moreover, since P4-Utils is only available on Linux, other OS users can run it in a linux VM.
We provide two different solutions for the P4-Utils VM and both are supported by a wide range of
operating systems:

- VirtualBox_
- QEMU_

__ #use-our-preconfigured-vm
__ #build-your-own-vm

You can choose to download and use one of our `preconfigured VMs`__ or to `build it by yourself`__.

.. Important::
    Whether you are building your own VM or you are using the preconfigured images, you still
    need to install one of the above virtualizer according to your VM choice.

Build your own VM
+++++++++++++++++

.. _Packer: https://www.packer.io/

To get started, you need to install the required software:

- VirtualBox_ or QEMU_
- Packer_

.. Note::
    Packer is a handy framework designed to automatically build custom VM images.

Clone the P4-Utils repository::

    git clone https://github.com/nsg-ethz/p4-utils

Go to the Packer configurations folder::

    cd p4-utils/vm

If you want to build the *VirtualBox VM*, execute::

    ./build-virtualbox.sh [--cpus 4] [--disk_size 25000] [--memory 4000] [--vm_name p4] [--username p4] [--password p4]

On the other hand, if you prefer the *QEMU VM*, run::

    ./build-qemu.sh [--cpus 4] [--disk_size 25000] [--memory 4000] [--vm_name p4] [--username p4] [--password p4]

.. Important::
    The default VMs configuration parameters are shown above. If you do not specify anything,
    they will be used to build your VM. However, please pass to the scripts the parameters
    that best fit your needs. In particular, we have that:

    - ``--cpus`` specifies the **number of cores** to use,
    - ``--disk_size`` is the **size of the disk** reserved by the VM in MBytes,
    - ``--memory`` is the amount of **RAM** to assign to the VM in MBytes,
    - ``--vm_name`` is the **name of the VM**,
    - ``--username`` is the **login username**,
    - ``--password`` is the **login password**.

The building process will generate the following files:

- If you chose the QEMU VM, in ``p4-utils/vm/output-ubuntu18044_qemu`` you will find
  a ``.qcow2`` file to use to set up your VM.
- If you chose the VirtualBox VM, in ``p4-utils/vm/output-ubuntu18044_vb`` you will
  find an ``.ova`` file to import in the VirtualBox VM manager.

Use our preconfigured VM
++++++++++++++++++++++++

To download our preconfiugred VMs, please click on the folllwing links:

- __ https://polybox.ethz.ch/index.php/s/QlrfHm7uYw6vISe

  `QEMU VM (Ubuntu 20)`__

- __ https://polybox.ethz.ch/index.php/s/9orcmetpNxOAhlI

  `Deprecated: QEMU VM (UBuntu 18.04)`__

- __ #

  `VirtualBox VM (unavailable)`__



Manual Installation
-------------------

__ #prerequisites

If you have already installed all the `requirements`__, you can simply
install P4-Utils using the following commands::

    git clone https://github.com/nsg-ethz/p4-utils
    cd p4-utils
    sudo ./install.sh

You can also uninstall it by running the command::

    sudo ./uninstall.sh

Prerequisites
+++++++++++++

P4-Utils depends on the following programs in the given order:

1. __ https://github.com/p4lang/PI

   `PI LIBRARY REPOSITORY`__ provides an implementation framework
   for a P4Runtime server. **It is required only for topologies with
   P4Runtime switches.**
2. __ https://github.com/p4lang/behavioral-model

   `BEHAVIORAL MODEL (bmv2)`__ contains the software implementation several
   variations of the behavioral model (e.g. ``simple_switch`` and
   ``simple_switch_grpc``).
3. __ https://github.com/p4lang/p4c

   `p4c`__ is a reference compiler for the P4 programming language that
   supports both **P4_14** and **P4_16**.
4. __ https://github.com/mininet/mininet

   `Mininet`__ allows to create a realistic virtual network, running real
   kernel, switch and application code, on a single machine (VM, cloud or native).
5. __ https://github.com/FRRouting/FRR

   `FRRouting`__ is a free and open source Internet routing protocol suite
   for Linux and Unix platforms. It implements BGP, OSPF, RIP, IS-IS, PIM,
   LDP, BFD, Babel, PBR, OpenFabric and VRRP, with alpha support for EIGRP
   and NHRP. Router nodes in P4-Utils are based on FRRouting. **It is required
   only for topologies with routers.**

__ https://github.com/nsg-ethz/p4-utils/blob/master/install-tools/install-p4-dev.sh

The manual installation process is quite long and cumbersome because of the
dependencies that are needed by P4-Utils. For this reason, we provide a `Bash
script`__ that automatically goes through every step.

.. Warning::
    The script has been tested with **Ubuntu 20.04 and Ubuntu 22.04** and the compiler
    **GCC 9.4**.

.. Important::
    With the following installation methods, you will download and install *Mininet*
    and the P4-Tools suite (P4-Utils, P4-Learning and their dependencies) in your
    user's home directory.

One-Step Automated Install
__________________________

To get started quickly and conveniently, you may want to install the P4-Tools suite
using the following command::

    curl -sSL https://raw.githubusercontent.com/nsg-ethz/p4-utils/master/install-tools/install-p4-dev.sh | bash

Alternative Installation Method
_______________________________

The main drawback of piping to `bash` is that you cannot review the code
that is going to run on your system. Therefore, we provide this alternative
methods that allows you to inspect the intallation script::

    wget -O install-p4-dev.sh https://raw.githubusercontent.com/nsg-ethz/p4-utils/master/install-tools/install-p4-dev.sh
    bash install-p4-dev.sh
