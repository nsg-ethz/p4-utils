# P4-Utils

P4-utils is an extension to Mininet that makes P4 networks easier to build, run and debug. P4-utils is strongly
inspired by [p4app](https://github.com/p4lang/p4app).

### Installation

First clone this repository:

```bash
git clone https://github.com/nsg-ethz/p4-utils.git
```

Run the installation script:

```bash
sudo ./install.sh
````

The install script will use `pip -e` to install the project in editable mode, meaning that every time you update the files
in this repository, either by pulling or doing local edits, the changes will automatically take place without the need of
installing the package again.

#### Uninstall

If you want to uninstall run:

```bash
sudo ./uninstall
```

This will remove all the scripts that were added to `/user/bin` as well as uninstall the python package using `pip`.

### How does it work ?

P4-utils creates virtual networks using mininet and extended nodes that run p4-enabled switches. To create hosts,
mininet uses a bash process running in a network namespace, in order words, all the processes that run within the
network namespaces have an isolated network stack. Switches are software-based switches like Open vSwitch, Linux Bridge,
or BMV2 switches. Mininet uses virtual ethernet pairs, which live in the Linux kernel to connect the emulated hosts and switches.

For more information see:

 * [Mininet](http://mininet.org/)
 * [Linux Namespaces]((https://blogs.igalia.com/dpino/2016/04/10/network-namespaces/))
 * [Virtual ethernet interfaces](http://man7.org/linux/man-pages/man4/veth.4.html)
 * [BMV2](https://github.com/p4lang/behavioral-model), [OVS](https://www.openvswitch.org/), [LinuxBridge](https://cloudbuilder.in/blogs/2013/12/02/linux-bridge-virtual-networking/).

### Features




## Usage

Topologies have to be specified in a file called `p4app.json`. An example can be found in `example/p4app.json`.


##


#### TODO: revise topology object so nothing weird is left.