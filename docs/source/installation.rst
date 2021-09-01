Installation
============

In order to work, P4-Utils needs different programs coming from different sources as prerequisites.
Since the installation process can be long and cumbersome, we provide different methods to make the
deployment easier for the users.

__ #virtual-machine

.. Note::
    Running P4-Utils in a completely separated environment can be beneficial: in this way, installation
    and execution errors, that may arise, will not affect the whole system. For this reason, we recommend
    using a `virtual machine`__.

Virtual Machine
---------------

.. _VirtualBox: https://www.virtualbox.org/

.. _QEMU: https://www.qemu.org/

P4-Utils can run in a virtual machine to keep its environment separated from the rest of the system.
Moreover, since P4-Utils is only available on Linux, other OS users can run it in a linux VM.
We provide two different solutions for the P4-Utils VM. Both are supported by a wide range of 
operating systems:

- VirtualBox_
- QEMU_

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
    Packer_ is a handy framework designed to automatically build custom VM images.

Clone the P4-Utils repository::

    git clone https://github.com/nsg-ethz/p4-utils

Go to the Packer configurations folder::

    cd p4-utils/vm

If you want to build the *VirtualBox VM*, execute::

    ./build-virtualbox.sh [--cpus 4] [--disk_size 25000] [--memory 4000] [--vm_name p4] [--username p4] [--password p4]

On the other hand, if you prefer the *QEMU VM*, run::

    ./build-qemu.sh [--cpus 4] [--disk_size 25000] [--memory 4000] [--vm_name p4] [--username p4] [--password p4]

.. Attention::
    The default VMs configuration parameters are shown above. If you do not specify anything
    they will be used to build your VM. However, please pass to the scripts the parameters
    that best fit your needs. In particular, we have that:

    - ``--cpus`` specifies the number of cores to use,
    - ``--disk_size`` is the size of the disk reserved by the VM in MBytes,
    - ``--memory`` is the amount of RAM to assign to the VM in MBytes,
    - ``--vm_name`` is the name of the VM,
    - ``--username`` is the login username,
    - ``--password`` is the login password.

Use our preconfigured VM
++++++++++++++++++++++++

To download our preconfiugred VMs, please click on the folllwing links:

- __ #

  `VirtualBox VM`__
- __ #

  `QEMU VM`__

Manual Installation
-------------------

__ #prerequisites

If you have already installed all the `requirements`__, you can simply
install P4-Utils using the following commands::

    git clone https://github.com/nsg-ethz/p4-utils
    cd p4-utils
    ./install.sh

Prerequisites
+++++++++++++

P4-Utils depends on the following programs in the given order:

1. __ https://github.com/p4lang/PI

   `PI LIBRARY REPOSITORY`__ (optional, if you want to use P4Runtime switches)
2. __ https://github.com/p4lang/behavioral-model
  
   `BEHAVIORAL MODEL (bmv2)`__
3. __ https://github.com/p4lang/p4c

   `p4c`__
4. __ https://github.com/mininet/mininet

   `Mininet`__
5. __ https://github.com/FRRouting/FRR

   `FRRouting`__ (optional, if you want to use routers)

The manual installation process is quite long and cumbersome because of the
dependencies that are needed by P4-Utils. For this reason, we provide a Bash
script that automatically goes through every step.

.. Attention::
    The script has been tested with **Ubuntu 18.04.4** and the compiler 
    **GCC 7.5**. Errors have been reported with newer versions.

In order to start the installation, you fist need to clone our repository::

    git clone https://github.com/nsg-ethz/p4-utils

Then, you have to go to the installation folder::

    cd p4-utils/install-tools

Finally, you can run the installation script::

    ./install-p4-dev.sh
