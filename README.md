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
 * [Linux Namespaces](https://blogs.igalia.com/dpino/2016/04/10/network-namespaces/)
 * [Virtual ethernet interfaces](http://man7.org/linux/man-pages/man4/veth.4.html)
 * [BMV2](https://github.com/p4lang/behavioral-model), [OVS](https://www.openvswitch.org/), [LinuxBridge](https://cloudbuilder.in/blogs/2013/12/02/linux-bridge-virtual-networking/).

### Features

P4-utils adds on top of minininet:

 * A command-line launcher (`p4run`) to instantiate networks.
 * A helper script (`mx`) to run processes in namespaces
 * Custom `P4Host` and `P4Switch` nodes (based on the ones provided in the [`p4lang`](https://github.com/p4lang) repo)
 * A very simple way of defining networks using json files (`p4app.json`).
 * Enhances mininet command-line interface: adding the ability of rebooting switches with updated p4 programs and configurations, without the need
 of restarting the entire network.
 * Saves the topology and features in an object that can be loded and queried to extract meaningful information (also build a `networkx` object out of the
 topology)
 * Re-implementation of the `runtime_CLI` and `simple_switch_CLI` as python objects to use in controller code.

### Usage

P4-utils can be executed by running the `p4run` command in a terminal. By default `p4run` will try to find a
topology description called `p4app.json` in your current path. However you can change that by using the `--config` option:

```bash
p4run --config <path_to_json_configuration>
```

You can see the complete list of options with the `-h` or `--help` options.

## Documentation

### Topology Description

To run any topology p4-utils needs a configuration file (`*.json`) that is used by `p4run` to know how to build and configure a
virtual network. All the possible options are listed below:

#### Global Configuration

Set of global settings defined in the first layer of the json object that describe the basic
configuration of our topology. For instance the switch type and compiler options can be set here.

##### `program:`

   * Type: String
   * Value: Path to p4 program
   * Default: None (required if not all switches have a p4 program defined).

   > Program that will be loaded onto all the switches unless a switch you specify a program in the switch conf.

##### `switch:`

   * Type: String
   * Value: path to bmv2 switch executable
   * Default: "simple_switch"

##### `compiler:`

   * Type: String
   * Value: P4 compiler to be used
   * Default: "p4c"

##### `options:`

   * Type: String
   * Value: Compiler options
   * Default: "--target bmv2 --arch v1model --std p4-16"

##### `switch_cli:`

   * Type: String
   * Value: Path to the switch CLI executable
   * Default: 'simple_switch_CLI'

##### `cli:`

   * Type: bool
   * Value: Enables the enhanced mininet CLI. If disabled, the topology will be destroyed right after being created.
   * Default: false

##### `pcap_dump:`

   * Type: bool
   * Value: if enabled a pcap file for each interfaced is saved at `./pcap`
   * Default: false

##### `enable_log:`

   * Type: bool
   * Value: if enabled a directory with CLI and switch logs is created at `.log`. For each switch two files are created, one includes the
   output of the CLI for the entries you populated using the p4-utils library. The second file `<sw_name>.log` includes packet traces that
   show how was the packet processed by the switch pipeline (i.e which branches were executed, table hit/miss, etc).
   * Default: false

### Special Modules

During the creation of the network 4 main blocks are used. To make p4utils more modular adding your
own block is allowed.

##### `topo_module`:

Module in charge of building the topology, amongs others it reads the topology object described in
the json configuration file and decides how to configure hosts and switches (i.e Mac and IP address assignment strategy).

##### `controller_module`

The controller module is in charge of configuring switches and populating its tables during
network creation.

##### `topodb_module`

The topologydb module is the object in charge of storing information about the topology and providing and API to extract
useful data.

##### `mininnet_module`

Modified version of the Mininet object. It simply adds a new attribute that contains `p4switches`.

**Setting your own module:**

By default each module will use the already defined objects in p4utils. If you want to add your own
implementation you can indicate that in the `json` file using the following syntax:

```javascript
  "topo_module | controller_module | topodb_module | minininet_module>"
  {
    "file_path": "<path to python object>",
    "module_name": "<name of python file>",
    "object_name": "<name of module object>"
  }
```

> For modules that are already included in the PYTHONPATH you don't have
to specify the "file_path".

#### Topology

The topology subsection of the configuration describes how the addresses are assigned,
the number of hosts and switches and how are they connected.

##### `assignment_strategy:`

When you use the default `topo_module` you can use different assignment strategies.
Assignment strategies are needed due to the fact that p4-switches can work
at any network layer (L2, L3, ...), and thus there is no way to automatically
configure the hosts, and switches without knowing what will switches do.

 * `l2`: all switches in the network are assumed to work at layer 2, thus
 all hosts get assigned to the same subnetwork.

 * `l3`: all switches in the network are assumed to work at layer 3, thus
 all links in the network form a different subnetwork. Hosts can only
 be connected to one switch device which is used to configure the host's gateway.

 * `mixed`: this is not a real l2 or l3 assignment strategy, but since p4 switches can work at any layer,
 it can be useful for easy prototyping. Hosts connected to the same switch will be assigned an ip within the same subnet. Hosts
 connected to another switch will belong to another subnet. Each hosts can only be connected to a single switch, which at the same time
 is assigned to be the L3 gatway.

 * `manual`: can be used when your topology will be formed by heterogeneous
 devices, you have to manually set the IP to each interface and host gateways.

 > By default l2 strategy is used

##### `auto_arp_tables:`

   * Type: bool
   * Value: if set, hosts get their ARP table automatically filled when the network is started. Note: hosts only
   learn the Mac addresses of other hosts within the same subnet.
   * Default: true

##### `auto_gw_arp:`

   * Type: bool
   * Value: if set, hosts get the ARP entry for the gate way route automatically configured. You need to enable this when your gw
   does not reply to ARP requests.
   * Default: true

##### `links:`

   * Type: list
   * Value: list of links that connect nodes in the topology.
   * Default: None

   Each link is of the form:
   ```python
   ["node1", "node2", {"delay": <in_ms>, "bw": <in_mbps>, "loss": <in_percent>, "queue_length": <num_packets>, "weight": <link_cost>}]
   ```

   Link characteristics are not mandatory. Also, not all the characteristics have to be defined, you can pick a subset. For the
   characteristics that are not set, the default values are:

   ```python
   link_dict = {'delay': '0ms',
                'bw': Inf,
                'loss': 0,
                'queue_length': 1000,
                'weight': 1
               }
   ```

   If you want to set the default value for all links, you can set the `default_<attribute>`. You have to set this parammeter at the topology level. Possible, defaults are: 
   `default_delay`, `default_bw`, `default_loss`, `default_queue_length`, `default_link_weight`.

##### `hosts:`

   * Type: dict
   * Value: dictionary where the keys are the hosts that have to be created.
   * Default: None
   * Host Conf Attributes:
       * `ip:` if using manual assignament strategy you can assign an ip to a host or use the keyword `auto` if hosts should be able to get IPs through a DHCP server.
       * `gw:` indicates the IP address of the gateway
       * `commands:` list of commands that will be executed at starting time. As now, only non blocking commands
        that terminate are allowed here. Example: "commands": ["echo 1 > /etc/config_file"]

   > TODO: add a way to start commands at hosts: this feature will be added soon.

##### `switches:`


   * Type: dict
   * Value: dictionary where the keys are switch names, and the values are switch confs.
   * Default: None
   * Switch Conf Attributes:
      * `cli_input:` path to the CLI-formatted text file that will be used to configure and populate the switch.
      * `program`: path to the p4 program that will be loaded onto the switch. If not specified, the global `program` path is used.
      * `<direct_neighbor>:` when using the manual IP assignment you can indicate the IP of the interface facing a neighboring node.

You can find a configuration example, that uses all the fields [here](./p4app_example.json)

### Topology Object

You can use the topology object by simply:

```python
from p4utils.utils.topology import Topology
topo = Topology(db="path_to_topology_db")

# Get all the switches
topo.get_p4switches().keys()
[u's3', u's2', u's1', u's4']

# One node information
topo.node('h1') #this also works topo['h1']
{u'gateway': u'10.1.1.1',
 u'interfaces_to_node': {u'h1-eth0': u's1'},
 u'interfaces_to_port': {u'h1-eth0': 0},
 u's1': {u'bw': None,
 u'delay': u'0ms',
 u'intf': u'h1-eth0',
 u'ip': u'10.1.1.2/24',
 u'mac': u'00:00:0a:01:01:02',
 u'queue_length': 1000,
 u'weight': 1},
 u'type': u'host'}
```

#### Methods Documentation

Some methods documented

* `get_p4switches()`: returns a dictionary where the keys are p4 switches names and values are information about the switch. You can use `get_p4switches().keys()` to
just get the switches names.
* `get_thrift_port(sw_name)`: returns the thrift port at which a `sw_name` is listening to. This can be used to establish a connection using the `SimpleSwitchAPI` object.
* `get_hosts_connected_to(sw_name)`: returns a list of all the host names connected to the switch `sw_name`.
* `get_host_ip(host_name)`: returns the ip address and subnet mask of host `host_name`. For example `10.0.1.2/24`.
* `get_host_mac(host_name)`: returns the mac address of host `host_name`.
* `node_to_node_port_num(node1, node2)`: returns the port index of `node1` facing `node2`. This index can be used to populate your forwarding table entries.
* `node_to_node_mac(node1, node2)`: returns the `mac` address of the interface from `node1` that connects with `node2`. This can be used to get next hop destination mac addresses.
* `get_shortest_paths_between_nodes(node1, node2)`: returns a list of the shortest paths between two nodes. The list includes the src and the destination and multiple equal cost paths
if found. For example, `get_shortest_paths_between_nodes('s1', 's2')` would return `[('s1', 's4', 's2'), ('s1', 's5', 's2')]` if two equal cost paths are found using `s4` and `s5` as next hops.

* `node_to_node_interface_ip(node1, node2)`: returns the IP address of the interface from `node1` connecting with `node2`. Note that the ip address includes the prefix len at the end `/x`.
* `get_interfaces_to_node(sw_name)`: returns a dictionary of all the interfaces as keys and the node they connect to as value. For example `{'s1-eth1': 'h1', 's1-eth2': 's2'}`.
* `interface_to_port(node, intf_name)`: returns the interface index of `intf_name` for `node`.

### Control Plane API

The control plane API is a wrapper (with some additions) over the original RuntimeCLI from [p4lang/bmv2](https://github.com/p4lang/behavioral-model/tree/master/tools). It allows
programmers to interface with the bmv2 thrift sever through a python object and by calling methods instead of using text throguh the CLI. Thus, this API allows programmers to write
more automated control plane functions.

While we write a more complete documentation you can check which functions are available to use directly at the source code:
[SimpleSwitchAPI](p4utils/utils/sswitch_API.py) and [RuntimeAPI](p4utils/utils/runtime_API.py)

**Note:** Some of the least used functions from the CLI have not been included in this API. However, some extra functions that do not exist in the CLI have
been added here.

**Important:** In the near future, this API should be replaced by the P4Runtime API, however do to lack of implementation for some functions at the time of
implementing this we chose to use the old thrift API.

