# Installation tools

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
