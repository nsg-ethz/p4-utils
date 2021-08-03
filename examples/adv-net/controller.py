"""Implement your controller in this file.

The existing controller already implements L2-forwarding to ensure connectivity.
Use this code as an example to get you started.
You are free to completely change this!

Tip:
For debugging, you can start this file in interactive mode.
This will execute the whole file, but then *keep* the python interpreter open,
allowing you to inspect objects and try out things!

```
$ python3 -i controller.py --topo <path to build/topology.db>
```

The controller will be available as the variable `control`.
"""
# pylint: disable=superfluous-parens,invalid-name

import argparse
import csv

from p4utils.utils.helper import load_topo
from p4utils.utils.sswitch_thrift_API import SimpleSwitchThriftAPI

class Controller(object):
    """The central controller for your p4 switches."""

    L2_BROADCAST_GROUP_ID = 1

    def __init__(self, topo, traffic=None):
        self.topo = load_topo(topo)
        if traffic is not None:
            # Parse traffic matrix.
            self.traffic = self._parse_traffic_file(traffic)
        else:
            self.traffic = []

        # Basic initialization. *Do not* change.
        self.controllers = {}
        self._connect_to_switches()
        self._reset_states()

        # Start main loop
        self.main()

    # Controller helpers.
    # ===================

    def _connect_to_switches(self):
        for p4switch in self.topo.get_p4switches():
            print("Connecting to %s" % p4switch)
            thrift_port = self.topo.get_thrift_port(p4switch)
            thrift_ip = self.topo.get_thrift_ip(p4switch)
            self.controllers[p4switch] = SimpleSwitchThriftAPI(
                thrift_port, thrift_ip)

    def _reset_states(self):
        for controller in self.controllers.values():
            controller.reset_state()

    @staticmethod
    def _parse_traffic_file(trafficpath):
        with open(trafficpath, 'r') as csvfile:
            dialect = csv.Sniffer().sniff(csvfile.read(1024))
            csvfile.seek(0)
            reader = csv.DictReader(csvfile, dialect=dialect)
            return list(reader)

    # Controller methods.
    # ===================

    def main(self):
        """Main controller method."""
        # Initialization of L2 forwarding. Feel free to modify.
        self.create_l2_multicast_group()
        self.add_l2_forwarding_rules()

        # while True
        #     do_something()

    def add_l2_forwarding_rules(self):
        """Add L2 forwarding groups to all switches.

        We check the topology object to get all connected nodes and their
        MAC addresses, and configure static rules accordingly.
        """
        for switch, controller in self.controllers.items():
            # Add broadcast rule.
            controller.table_add("l2_forward", "broadcast",
                                 ["ff:ff:ff:ff:ff:ff/48"])

            # Add rule for connected host.
            my_host = self.topo.get_hosts_connected_to(switch)[0]
            host_mac = self.topo.node_to_node_mac(my_host, switch)
            host_port = self.topo.node_to_node_port_num(switch, my_host)
            controller.table_add("l2_forward", "l2_forward_action",
                                 [str(host_mac)+"/48"], [str(host_port)])

            # Add rules for connected routers.
            for router in self.topo.get_routers_connected_to(switch):
                router_mac = self.topo.node_to_node_mac(router, switch)
                router_port = self.topo.node_to_node_port_num(switch, router)
                controller.table_add("l2_forward", "l2_forward_action",
                                     [str(router_mac)+"/48"], [str(router_port)])

    def create_l2_multicast_group(self):
        """Create a multicast group to enable L2 broadcasting."""
        for switch, controller in self.controllers.items():
            controller.mc_mgrp_create(self.L2_BROADCAST_GROUP_ID)
            port_list = []

            # Get host port.
            my_host = self.topo.get_hosts_connected_to(switch)[0]
            port_list.append(self.topo.node_to_node_port_num(switch, my_host))

            # Get router ports.
            for router in self.topo.get_routers_connected_to(switch):
                port_list.append(
                    self.topo.node_to_node_port_num(switch, router))

            # Update group.
            controller.mc_node_create(0, port_list)
            controller.mc_node_associate(1, 0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--topo', help='Path of topology.db.',
                        type=str, required=False,
                        default="./topology.json")
    parser.add_argument('--traffic', help='Path of traffic scenario.',
                        type=str, required=False,
                        default=None)
    args = parser.parse_args()

    control = Controller(args.topo, args.traffic)
