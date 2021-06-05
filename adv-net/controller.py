"""
Implement your controller in this file.

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
import time
import random

from p4utils.utils.helper import load_topo
from p4utils.utils.sswitch_thrift_API import SimpleSwitchThriftAPI

class Controller(object):
    """The central controller for your p4 switches."""

    # Multicast groups IDs
    L2_BROADCAST_GROUP_ID = 1
    L2_MULTICAST_GROUP_ID = 2
    # First 15 MPLS labels are reserved
    LABEL_OFFSET = 16
    # Set check interval for failures (seconds)
    CHECK_INTERVAL = 0.25
    # Set failure time to assess link status (seconds)
    FAILURE_TIME = 0.5
    # Set check time for failed links testing (seconds)
    CHECK_TIME = 10

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

        # Subflows reservations
        self.current_reservations = {}
        # Flows activity diictionary
        self.flows_activity = {}
        # Link capacity dictionary
        self.links_capacity = self.build_links_capacity()
        # Capacity of links considering only gold subflows
        self.links_capacity_g = self.build_links_capacity()
        # Capacity of links considering only gold and silver subflows
        self.links_capacity_gs = self.build_links_capacity()

        # Sorted path dictionary (cache)
        self.sorted_paths = {}

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
        with open(trafficpath, 'rb') as csvfile:
            dialect = csv.Sniffer().sniff(csvfile.read(1024))
            csvfile.seek(0)
            reader = csv.DictReader(csvfile, dialect=dialect)
            return list(reader)

    # Controller methods.
    # ===================

    def main(self):
        """
        Main controller method.
        """
        # Create L2 multicast groups for ARP and OSPF
        self.create_l2_multicast_groups()
        # Add L2 forwarding rules into the switches tables
        self.add_l2_forwarding_rules()
        # Add L3 forwarding rules into the switches tables
        self.add_l3_forwarding_rules()
        # Associate switches ports with MPLS labels
        self.set_default_mpls_labels()
        # Get flows groups
        gold_flows, silver_flows, bronze_flows = self.group_flows_by_type()
        # Create reservations for the flows groups
        self.create_reservations(gold_flows)
        self.create_reservations(silver_flows)
        self.create_reservations(bronze_flows)
        # Create backup subflows for the reserved flows
        self.create_backups(128, 5)
        self.create_backups(64, 3)
        # Failure detection
        self.run_link_failure_detection(self.CHECK_INTERVAL, self.FAILURE_TIME, self.CHECK_TIME)

    def reset_backups(self, subflow_id):
        """
        This function resets all the active backup subflows lower in the
        hierarchy to the default status (not active and working).

        Args:
            subflow_id (int): the id of the parent subflow
        """
        # Get backup subflow id
        backup_id = self.current_reservations[subflow_id]['backup_id']
        # Check if the backup is set
        if backup_id != None:
            # Check if the backup subflow is active
            if self.current_reservations[backup_id]['active'] == 1:
                # Deactivate backup subflow
                self.current_reservations[backup_id]['active'] = 0
                # Reset failures count of the backup subflow
                self.current_reservations[backup_id]['n_failures'] = 0
            # Recursively reset backups
            self.reset_backups(backup_id)


    def run_link_failure_detection(self, check_interval, failure_time, check_time):
        """
        This function implements a loop to check the status of active subflows.

        Args:
            check_interval (float): seconds between subsequent checks
            failure_time (float): time after not having received packets needed
                                  to set a subflow as failed.
            check_time (float): after this amount of time a failed subflow which
                                has an active parent is checked again for status.
        """
        # Initialize empty dictionary
        tmp_flows_activity = {}
        # Log
        print("Starting failure detection...")
        # Iterate forever
        while True:
            # Initialize empty list
            updated_flows = []
            # Iterate over self.current_reservations
            for subflow_id, res in self.current_reservations.items():
                # Get ingress switch
                ingress_switch = res['path'][0]
                # Get flow_id
                flow_id = res['flow_id']
                # Get number of sent packets for the current flow
                new_count = self.controllers[ingress_switch].register_read("flow_packets_counter", flow_id)
                # Check if the flow has not  been already updated
                if flow_id not in updated_flows:
                    # Update temporary flows activity
                    tmp_flows_activity[flow_id] = new_count
                    # Append flow_id to updated flows
                    updated_flows.append(flow_id)
                # If new packets have been sent
                if new_count != self.flows_activity[flow_id]:
                    # Get egress switch
                    egress_switch = res['path'][-1]
                    # If the reservation is active
                    if res['active'] == 1:
                        # Get packets count for the current subflow
                        received_count = self.controllers[egress_switch].register_read("subflow_packets_counter", subflow_id)
                        # If new packets have been received
                        if received_count > 0:
                            # Set subflow_packets_counter to zero for the current subflow
                            self.controllers[egress_switch].register_write("subflow_packets_counter", subflow_id, 0)
                            # Reset failures count of the current subflow
                            self.current_reservations[subflow_id]['n_failures'] = 0
                        # If no new packet has been received
                        else:
                            # Increment failure count
                            self.current_reservations[subflow_id]['n_failures'] += 1
                            # Check number of subsequent failures
                            if self.current_reservations[subflow_id]['n_failures'] >= int(failure_time/check_interval):
                                # Check if backup path is available
                                if res['backup_id'] != None:
                                    # Activate backup subflow
                                    self.current_reservations[res['backup_id']]['active'] = 1
                                    # Reset failures count of the backup subflow
                                    self.current_reservations[res['backup_id']]['n_failures'] = 0
                                    # Set current subflow to failed
                                    self.controllers[ingress_switch].register_write("subflow_failure_status", subflow_id, 1)
                                    # Deactivate current subflow
                                    self.current_reservations[subflow_id]['active'] = 0
                    # If the reservation is not active
                    else :
                        # If the subflow has a backup
                        if res['backup_id'] != None:
                            # If the backup is active
                            if self.current_reservations[res['backup_id']]['active'] == 1:
                                # Increment subflow failed count
                                self.current_reservations[subflow_id]['n_failures'] += 1
                                # If the subflow has been found failed for more than check_time
                                if self.current_reservations[subflow_id]['n_failures'] >= int(check_time/check_interval):
                                    # Set current subflow as working (needed to check if the link recovered)
                                    self.controllers[ingress_switch].register_write("subflow_failure_status", subflow_id, 0)
                                    # Activate current subflow
                                    self.current_reservations[subflow_id]['active'] = 1
                                    # Reset failures count of the current subflow
                                    self.current_reservations[subflow_id]['n_failures'] = 0
                                    # Reset active backup subflows
                                    self.reset_backups(subflow_id)
            # Iterate over flow_id and counts
            for flow_id, count in tmp_flows_activity.items():
                # Update old_sent_count
                self.flows_activity[flow_id] = count
            # Sleep for check_interval seconds
            time.sleep(check_interval)

    def add_l2_forwarding_rules(self):
        """
        Add L2 forwarding groups to all switches.

        We check the topology object to get all connected nodes and their
        MAC addresses, and configure static rules accordingly.
        """
        for switch, controller in self.controllers.items():
            # Add broadcast rule.
            controller.table_add("l2_forward", "broadcast",
                                 ["ff:ff:ff:ff:ff:ff/48"])

            # Add rules for multicast L2 packets (e.g. OSPF).
            controller.table_add("l2_forward", "multicast",
                                 ["01:00:5e:00:00:00/25"])

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

    # Required for ARP requests and to exploit OSPF via L2 switches (enabled
    # forwarding of multicast MAC addresses). OSPF exploitation was not used in
    # the project.
    def create_l2_multicast_groups(self):
        """
        Create a multicast group to enable L2 broadcasting and multicasting.
        """
        for switch, controller in self.controllers.items():
            controller.mc_mgrp_create(self.L2_BROADCAST_GROUP_ID)
            controller.mc_mgrp_create(self.L2_MULTICAST_GROUP_ID)

            # Intitialize broadcast and multicast port lists
            bcast_port_list = []
            mcast_port_list = []

            # Get host
            my_host = self.topo.get_hosts_connected_to(switch)[0]
            # Broadcast group includes host port
            bcast_port_list.append(self.topo.node_to_node_port_num(switch, my_host))

            # Iterate over routers
            for router in self.topo.get_routers_connected_to(switch):
                # Get router port
                port = self.topo.node_to_node_port_num(switch, router)
                # Broadcast group includes router ports
                bcast_port_list.append(port)
                # Multicast group includes router ports
                mcast_port_list.append(port)

            # Create nodes
            bcast_handle = controller.mc_node_create(0, bcast_port_list)
            mcast_handle = controller.mc_node_create(0, mcast_port_list)
            # Associate with groups
            controller.mc_node_associate(self.L2_BROADCAST_GROUP_ID, bcast_handle)
            controller.mc_node_associate(self.L2_MULTICAST_GROUP_ID, mcast_handle)

    def add_l3_forwarding_rules(self):
        """
        Generate IPv4 routes for switch-switch paths, routers and hosts.
        """
        # Iterate over switches
        for switch in self.topo.get_p4switches():
            # Intitialize switch controller
            switch_controller = self.controllers[switch]
            # Iterate over neighbors
            for neighbor in self.topo.get_neighbors(switch):
                # Get the switch port which faces the host
                switch_port = self.topo.node_to_node_port_num(switch, neighbor)
                # Get destination MAC
                dst_mac = self.topo.node_to_node_mac(neighbor, switch)
                # Get source MAC
                src_mac = self.topo.node_to_node_mac(switch, neighbor)
                # If the neighbor is a host
                if self.topo.isHost(neighbor):
                    # Get host IP
                    dest_ip = self.topo.get_host_ip(neighbor)
                    # Add entry in the ipv4_forward table of the switch
                    switch_controller.table_add("ipv4_forward", "ipv4_forward_action", [str(dest_ip)+"/32"], [str(dst_mac), str(src_mac), str(switch_port)])
                # If the neighbor is a router
                elif self.topo.isRouter(neighbor):
                    # Get router interface IP
                    dest_ip = self.topo.node_to_node_interface_ip(neighbor, switch).split("/")[0]
                    # Add entry in the ipv4_forward table of the switch
                    switch_controller.table_add("ipv4_forward", "ipv4_forward_action", [str(dest_ip)+"/32"], [str(dst_mac), str(src_mac), str(switch_port)])
                # If the the neighbor is a switch
                else:
                    # Iterate over hosts connected to the neighbor switch
                    for host in self.topo.get_hosts_connected_to(neighbor):
                        # Get host IP
                        dest_ip = self.topo.get_host_ip(host)
                        # Add entry in the ipv4_forward table of the switch
                        switch_controller.table_add("ipv4_forward", "ipv4_forward_action", [str(dest_ip)+"/24"], [str(dst_mac), str(src_mac), str(switch_port)])

    # This function was not used in the project because of poor performance.
    def add_ipv4_multipath(self):
        """
        Generate load balancing for IPv4 packets.
        """
        # Iterate over switches
        for switch in self.topo.get_p4switches():
            # Intitialize switch controller
            switch_controller = self.controllers[switch]
            # Initialize list of neighboring routers
            neighbor_routers = self.topo.get_routers_connected_to(switch)
            # Initialize list of neighboring hosts
            neighbor_hosts = self.topo.get_hosts_connected_to(switch)
            # Add entry in the ipv4_forward table of the switch for multipath
            switch_controller.table_add("ipv4_forward", "ipv4_multipath_select", ["0.0.0.0/0"], [str(len(neighbor_routers))])
            # Iterate over neighboring hosts
            for host in neighbor_hosts:
                # Get host port
                host_port = self.topo.node_to_node_port_num(switch, host)
                # Iterate over routers
                for i in range(len(neighbor_routers)):
                    # Get the switch port which faces the host
                    switch_port = self.topo.node_to_node_port_num(switch, neighbor_routers[i])
                    # Get destination MAC
                    dst_mac = self.topo.node_to_node_mac(neighbor_routers[i], switch)
                    # Get source MAC
                    src_mac = self.topo.node_to_node_mac(switch, neighbor_routers[i])
                    # Add entra in the ipv4_multipath table
                    switch_controller.table_add("ipv4_multipath", "ipv4_forward_action", [str(i), str(host_port)], [str(dst_mac), str(src_mac), str(switch_port)])

    def set_default_mpls_labels(self):
        """
        Set the default MPLS labels in the switches forwarding table. This
        function associates each port with a label.
        """
        # Iterate over switches
        for switch in self.topo.get_p4switches():
            # Get switch controller
            controller = self.controllers[switch]
            # Iterate over neighbors
            for neighbor in self.topo.get_neighbors(switch):
                # Get destination port
                port = self.topo.node_to_node_port_num(switch, neighbor)
                # Compute label as port number plus offset
                label = port + self.LABEL_OFFSET
                # Get destination MAC
                dst_mac = self.topo.node_to_node_mac(neighbor, switch)
                # Get source MAC
                src_mac = self.topo.node_to_node_mac(switch, neighbor)
                # Add rule in the case of forwarding
                controller.table_add("mpls_forward", "mpls_forward_action", [str(label)], [str(dst_mac), str(src_mac), str(port)])

    def build_links_capacity(self):
        """
        Builds link capacities dictionary.

        Returns:
            dict: {edge: bw}
        """
        links_capacity = {}
        # Iterates all the edges in the topology formed by switches and routers
        for src, dst in self.topo.edges:
            bw = self.topo.edges[(src, dst)]['bw']
            # Exclude links between edges and hosts
            if not (self.topo.isHost(src) or self.topo.isHost(dst)):
                # add both directions
                links_capacity[(src, dst)] = bw
                links_capacity[(dst, src)] = bw

        return links_capacity

    def get_sorted_paths(self, src, dst):
        """
        Gets all paths between src, dst
        sorted by length. This function uses the internal networkx API.

        Args:
            src (str): src name
            dst (str): dst name

        Returns:
            list: paths between src and dst
        """
        # Check if this request has not been done before
        if (src, dst) not in self.sorted_paths.keys():
            # Get paths
            paths = self.topo.get_all_paths_between_nodes(src, dst)
            # trimp src and dst
            paths = [x[1:-1] for x in paths]
            # Add list to dictionary
            self.sorted_paths[(src, dst)] = paths
        # If this request is cached
        else:
            # Get cache
            paths = self.sorted_paths[(src, dst)]
        # Return results
        return paths

    def check_if_reservation_fits(self, path, bw, tos=32):
        """
        Checks if a the candidate reservation fits in the current
        state of the network. Using the path of switches, checks if all
        the edges (links) have enough space. Otherwise, returns False.

        Args:
            path (list): list of switches and routers
            bw (float): requested bandwidth in mbps
            tos (int): consider only flows with priority larger than or
                       equal to the provided tos

        Returns:
            bool: true if allocation can be performed on path
        """
        # If tos is 32 consider all flows
        links_capacity = self.links_capacity
        # Check if tos is larger than 64
        if tos >= 64:
            # Consider all flows but bronze ones
            links_capacity = self.links_capacity_gs
            # Check if tos is larger than 128
            if tos >= 128:
                # Consider only gold flows
                links_capacity = self.links_capacity_g
        # Iterate over all the nodes along the edge
        for i in range(len(path) - 1):
            # Select link between two nodes
            link = (path[i], path[i + 1])
            # Check whether the reservation does not fit in the link
            if links_capacity[link] - bw < 0:
                # Return False since the path is not available
                return False
        # Return True since all the links were tested successfully
        return True

    def add_link_capacity(self, path, bw, tos=32):
        """
        Adds bw capacity to a all the edges along path. This
        function is used when an allocation is removed.

        Args:
            path (list): list of switches and routers
            bw (float): requested bandwidth in mbps
            tos (int): tos of the reserved bandwidth
        """
        # Iterate over all the nodes along the edge
        for i in range(len(path) - 1):
            # Select link between two nodes
            link = (path[i], path[i + 1])
            # Add capacity to link
            self.links_capacity[link] += bw
            # Check if it is a silver flow
            if tos >= 64:
                # Add capacity to link
                self.links_capacity_gs[link] += bw
                # Check if it is a gold flow
                if tos >= 128:
                    # Add capacity to link
                    self.links_capacity_g[link] += bw

    def sub_link_capacity(self, path, bw, tos=32):
        """
        Subtracts bw capacity to a all the edges along path. This
        function is used when an allocation is added.

        Args:
            path (list): list of switches and routers
            bw (float): requested bandwidth in mbps
            tos (int): tos of reserved bandwidth
        """
        # Iterate over all the nodes along the edge
        for i in range(len(path) - 1):
             # Select link between two nodes
             link = (path[i], path[i + 1])
             # Subtract capacity from link
             self.links_capacity[link] -= bw
             # Check if it is a silver flow
             if tos >= 64:
                 # Subtract capacity to link
                 self.links_capacity_gs[link] -= bw
                 # Check if it is a gold flow
                 if tos >= 128:
                     # Subtract capacity to link
                     self.links_capacity_g[link] -= bw

    def get_available_paths(self, src, dst, bw, tos=32, shuffle=False, greedy=True):
        """
        Checks all paths from src to dst and gives all the
        paths that can allocate bw.

        Args:
            src (str): src name
            dst (str): dst name
            bw (float): requested bandwidth in mbps
            tos (int): consider only flows with priority larger than or
                       equal to the provided tos
            shuffle (bool) : whether to shuffle or not the results
            greedy (bool): whether to cosider all paths with some
                           residual available bandwidth

        Returns:
            list: available paths (empty if no one is available)
        """
        # Initialize empty lists
        av_paths = []
        av_paths_greedy = []
        # Iterate over all the possible paths
        for path in self.get_sorted_paths(src, dst):
            # Check if the path is available
            if self.check_if_reservation_fits(path, bw, tos):
                # Append the path to the available ones
                av_paths.append(path)
                av_paths_greedy.append(path)
            # Check for paths with some residual bandwidth available
            elif self.check_if_reservation_fits(path, 0, tos):
                # Append the path to the available ones
                av_paths_greedy.append(path)
        # Check if greedy path selection is active
        if greedy:
            # Check if the list is empty
            if len(av_paths) == 0:
                # Use av_paths_greedy
                av_paths = av_paths_greedy
        # If shuffle is True
        if shuffle:
            # Shuffle available paths
            random.shuffle(av_paths)
        # Return all the available paths
        return av_paths

    def get_mpls_labels_for_path(self, path):
        """
        Get MPLS labels for the given path. The path list does not include the
        hosts. Indeed we use penultimate hop popping.

        Args:
            path (list): list of switches and routers

        Returns:
            labels (list): list of MPLS labels to forward traffic
        """
        # Initialize labels list
        labels = []
        # Iterate over all pair of switches and routers in the path
        for node_from, node_to in zip(path, path[1:]):
            # Get node_from port number to reach node_to
            port = self.topo.node_to_node_port_num(node_from, node_to)
            # Compute label as port number plus offset
            label = port + self.LABEL_OFFSET
            # Append label to the label list
            labels.append(str(label))
        # Return labels list
        return labels

    def group_flows_by_type(self):
        """
        Return traffic flows by type.

        Returns:
            gold_flows (list): list of all the gold traffic flows
            silver_flows (list): list of all the silver traffic flows
            bronze_flows (list): list of all the bronze traffic flows
        """
        # Initialize empty lists
        gold_flows = []
        silver_flows = []
        bronze_flows = []
        # Iterate over all the flows
        for flow in self.traffic:
            # If the ToS is equal to 128, it is a gold flow
            if int(flow["tos"]) == 128:
                # Append flow to gold_flows list
                gold_flows.append(flow)
            # If the ToS is equal to 64, it is a silver flow
            elif int(flow["tos"]) == 64:
                # Append flow to silver_flows list
                silver_flows.append(flow)
            # Else it is a bronze flow
            else:
                # Append flow to bronze_flows list
                bronze_flows.append(flow)
        # Return flows by type
        return gold_flows, silver_flows, bronze_flows

    def path_edges(self, path):
        """
        This function returns all the edges belonging to the specified path.

        Args:
            path (list): list of switches and routers

        Returns:
            edges (list): list of edges (tuples of nodes)
        """
        # Initialize empty lists
        edges = []
        # Iterate over all pair of switches and routers in path
        for node_from, node_to in zip(path, path[1:]):
            # Append edge to edges
            edges.append((node_from, node_to))
        # Return edges
        return edges

    def count_shared_links(self, edges_1, edges_2):
        """
        This function returns the number of links that are shared among path_1
        and path_2.

        Args:
            edges_1 (list): list of edges of path_1
            edges_2 (list): list of edges of path_2

        Returns:
            n_shared_links (int): number of links shared among path_1 and path_2
        """
        # Initialize n_shared_links
        n_shared_links = 0
        # Iterate over edge_1
        for edge_1 in edges_1:
            # Check if it is a shared link
            if edge_1 in edges_2:
                # Increment number of shared links
                n_shared_links += 1
        # Return computed value
        return n_shared_links

    def add_reservation(self, path, src, dst, rate, n_splits, tos, flow_id, subflow_id):
        """
        This is an helper function of create_reservations() which handles the
        creation of the table rules and registers the reservation into
        self.current_reservations dict.

        Args:
            path (list): list of switches and routers
            src (str): source
            dst (str): destination
            rate (int): rate of the parent flow
            n_splits (int): number of subflows
            tos (int): tos
            flow_id (int): unique flow id
            subflow_id (int): unique subflow
        """
        # Get destination host ip
        dst_ip = self.topo.get_host_ip(dst)
        # Get ingress switch
        ingress_switch = path[0]
        # Get path labels
        labels = self.get_mpls_labels_for_path(path)
        # Append last label with the subflow identifier (plus the label offset)
        labels.append(str(subflow_id + self.LABEL_OFFSET))
        # Check if this is the first reserved subflow of the flow
        if subflow_id == flow_id:
            # Add entry to flows_activity dictionary
            self.flows_activity[flow_id] = 0
            # Add ecmp selection rule to ipv4_forward table in the ingress switch
            self.controllers[ingress_switch].table_add("ipv4_forward",
                                                       "mpls_ecmp_select",
                                                       [str(dst_ip)+"/32"],
                                                       [str(n_splits), str(flow_id)])
        # Add fec rule to mpls_fec table in the ingress switch
        self.controllers[ingress_switch].table_add("mpls_fec",
                                                   "mpls_ingress_{}_hop".format(len(labels)),
                                                   [str(subflow_id)],
                                                   labels)
        # Add reservation (some fields may be useless, cleanup later)
        self.current_reservations[subflow_id] = {
                                                    'active': 1,                # normal subflows start active
                                                    'backup_id': None,          # Backup subflow id
                                                    'dst': dst,
                                                    'flow_id': flow_id,
                                                    'n_failures': 0,            # Number of subsequent failures checks
                                                    'parent_id': None,          # Parent subflow id
                                                    'path': path,
                                                    'rate': rate,
                                                    'n_splits': n_splits,
                                                    'src': src,
                                                    'tos': tos
                                                }
        # Subtract used capacity from the links of the path
        self.sub_link_capacity(path, rate/n_splits, tos)

    def add_backup(self, path, backup_id, parent_id):
        """
        This is an helper function of create_backups() which handles the
        creation of the table rules and registers the reservation into
        self.current_reservations dict.

        Args:
            path (list): list of switches and routers
            parent_id (int): subflow id of parent subflow
            backup_id (int): subflow id of this backup subflow
        """
        # Get ingress switch
        ingress_switch = path[0]
        # Get path labels
        labels = self.get_mpls_labels_for_path(path)
        # Append last label with the subflow identifier (plus the label offset)
        labels.append(str(backup_id + self.LABEL_OFFSET))
        # Add fec rule to mpls_fec table in the ingress switch
        self.controllers[ingress_switch].table_add("mpls_fec",
                                                   "mpls_ingress_{}_hop".format(len(labels)),
                                                   [str(backup_id)],
                                                   labels)
        # Add backup_id to the backup_subflows register at index parent_id
        self.controllers[ingress_switch].register_write("backup_subflows", parent_id, backup_id)
        # Add reservation (some fields may be useless, cleanup later)
        self.current_reservations[backup_id] = {
                                                    'active': 0,                                                    # Backup subflows do not start active
                                                    'backup_id': None,                                              # Backup subflow id
                                                    'dst': self.current_reservations[parent_id]['dst'],
                                                    'n_failures': 0,                                                # Number of subsequent failures checks
                                                    'flow_id': self.current_reservations[parent_id]['flow_id'],
                                                    'parent_id': parent_id,                                         # Parent subflow id
                                                    'path': path,
                                                    'rate': self.current_reservations[parent_id]['rate'],
                                                    'n_splits': self.current_reservations[parent_id]['n_splits'],
                                                    'src': self.current_reservations[parent_id]['src'],
                                                    'tos': self.current_reservations[parent_id]['tos']
                                                }
        # Add backup entry in the parent reservation
        self.current_reservations[parent_id]['backup_id'] = backup_id
        # Subtract used capacity from the links of the path
        self.sub_link_capacity(path, self.current_reservations[parent_id]['rate']/self.current_reservations[parent_id]['n_splits'],  self.current_reservations[parent_id]['tos'])

    def create_backups(self, tos, n_backups):
        """
        Create mpls backup reservations for subflows with the same ToS. This function provides
        backup paths for the flows.

        Args:
            tos (int): tos of subflows
            n_backups (int): number of backups per subflow
        """
        # Iterate over backups
        for backup in range(n_backups):
            # Iterate over flow groups
            for subflow_id, res in self.current_reservations.items():
                # Set the flow_id (the unique flow identifier)
                backup_id = max(self.current_reservations.keys() + [0]) + 1
                # If the tos of the subflow is equal to the specified tos and
                # the subflow has not a backup_id specified yet
                if res['tos'] == tos and res['backup_id'] == None:
                    # Initialize temporary variable
                    subflow_id_tmp = subflow_id
                    # Iterate while the selected reservation has no parent
                    while subflow_id_tmp != None:
                    # Remove bandwidth allocation for current path
                        self.add_link_capacity(self.current_reservations[subflow_id_tmp]['path'],
                                               res['rate']/res['n_splits'],
                                               tos)
                        # Update subflow_id
                        subflow_id_tmp = self.current_reservations[subflow_id_tmp]['parent_id']
                    # Get available paths by considering flows with priority higher or equal
                    av_paths = self.get_available_paths(res['src'], res['dst'], res['rate']/res['n_splits'], tos)
                    # Initialize temporary variable
                    subflow_id_tmp = subflow_id
                    # Iterate while the selected reservation has no parent
                    while subflow_id_tmp != None:
                        # Restore bandwidth allocation for current path
                        self.sub_link_capacity(self.current_reservations[subflow_id_tmp]['path'],
                                               res['rate']/res['n_splits'],
                                               tos)
                        # Update subflow_id
                        subflow_id_tmp = self.current_reservations[subflow_id_tmp]['parent_id']
                    # Initialize an empty list
                    evaluations = []
                    # Iterate over av_paths
                    for av_path in av_paths:
                        # Set overall shared links count to zero
                        n_shared_links = 0
                        # Get edges from av_path
                        av_path_edges = self.path_edges(av_path)
                        # Initialize n_shared_links
                        n_shared_links = 0
                        # Initialize temporary variable
                        subflow_id_tmp = subflow_id
                        # Reset variable
                        to_continue = False
                        # Iterate while the selected reservation has no parent
                        while subflow_id_tmp != None:
                            # Get edges from res_path
                            res_path_edges = self.path_edges(self.current_reservations[subflow_id_tmp]['path'])
                            # Compute partial shared edges
                            n_shared_links_tmp = self.count_shared_links(av_path_edges, res_path_edges)
                            # Check if n_shared_links_tmp is different from the length of the reserved path
                            if n_shared_links_tmp < len(res_path_edges):
                                # Compute the number of shared links and add the to the sum
                                n_shared_links += n_shared_links_tmp
                                # Update subflow_id
                                subflow_id_tmp = self.current_reservations[subflow_id_tmp]['parent_id']
                            # If the backup path is equal to the parent path
                            else:
                                # Check another available path
                                to_continue = True
                                # Break loop
                                break
                        # Check to_continue variable
                        if to_continue:
                            # Continue loop
                            continue
                        # Add the record to the list
                        evaluations.append({
                                            'path': av_path,
                                            'n_shared_links': n_shared_links
                                           })
                        # If the found path has zero shared links
                        if n_shared_links == 0:
                            # Break loop
                            break
                    # If av_paths is not empty
                    if len(evaluations) > 0:
                        # Best path initialization
                        best_path_shared_links = evaluations[0]['n_shared_links']
                        best_path = evaluations[0]['path']
                        # Iterate over evaluated_paths
                        for evaluation in evaluations:
                            # Check if the current path is better
                            if evaluation['n_shared_links'] < best_path_shared_links:
                                # Update best path
                                best_path_shared_links = evaluation['n_shared_links']
                                best_path =  evaluation['path']
                        # Add reservation
                        self.add_backup(best_path, backup_id, subflow_id)

    def create_reservations(self, flows_group, n_splits=None):
        """
        Create mpls reservations for a given flows group. This function provides
        multipath balance for the flows. The default setting is that each flow
        in the flow group is split into 1 Mbps subflows. This can be overridden
        by passing the number of splits as argument.

        Args:
            flows_group (list): list of flows
            n_splits (int): number of subflows per flow (optional)
        """
        # Iterate over flow groups
        for flow in flows_group:
            # Set the flow_id (the unique flow identifier)
            flow_id = max(self.current_reservations.keys() + [0]) + 1
            # Get flow source
            src = flow['src']
            # Get flow destination
            dst = flow['dst']
            # Get tos
            tos = int(flow['tos'])
            # Get flow rate (in Mbps)
            rate = float(flow['rate'][:-1])
            # If n_splits is not specified
            if n_splits == None or n_splits <= 0:
                #  Check if the flows_group is gold
                if tos == 128:
                    # Split gold in subflows of 0.33 Mbps
                    n_splits = max(int(round(rate))*3, 1)
                # If the flow is silver
                elif tos == 64:
                    # Split silver in subflows of 0.5 Mbps
                    n_splits = max(int(round(rate))*2, 1)
                # If the flow is bronze
                else:
                    # Split bronze in subflows of 1 Mbps
                    n_splits = max(int(round(rate)), 1)
            # Iterate over n_splits subflows
            for subflow in range(n_splits):
                # Get all the available paths that can fit a subflow
                av_paths = self.get_available_paths(src, dst, rate/n_splits, tos)
                # If av_paths is not empty
                if len(av_paths) > 0:
                    # Compute subflow_id
                    subflow_id = flow_id + subflow
                    # If it is the first reservation made
                    if len(self.current_reservations.keys()) == 0:
                        # Get first available path
                        path = av_paths[0]
                        # Add reservation
                        self.add_reservation(path, src, dst, rate, n_splits, tos, flow_id, subflow_id)
                    # If other reservations were made before
                    else:
                        # Initialize an empty list
                        evaluations = []
                        # Iterate over av_paths
                        for av_path in av_paths:
                            # Set overall shared links count to zero
                            n_shared_links = 0
                            # Get edges from av_path
                            av_path_edges = self.path_edges(av_path)
                            # Iterate over reservations
                            for _, res in self.current_reservations.items():
                                # Consider only reserved paths for the same flow
                                if res['flow_id'] == flow_id:
                                    # Get edges from res_path
                                    res_path_edges = self.path_edges(res['path'])
                                    # Compute the number of shared links and add it to the count
                                    n_shared_links += self.count_shared_links(av_path_edges, res_path_edges)
                            # Add the record to the list
                            evaluations.append({
                                                'path': av_path,
                                                'n_shared_links': n_shared_links
                                               })
                            # If the found path has zero shared links
                            if n_shared_links == 0:
                                # Break loop
                                break
                        # Best path initialization
                        best_path_shared_links = evaluations[0]['n_shared_links']
                        best_path = evaluations[0]['path']
                        # Iterate over evaluated_paths
                        for evaluation in evaluations:
                            # Check if the current path is better
                            if evaluation['n_shared_links'] < best_path_shared_links:
                                # Update best path
                                best_path_shared_links = evaluation['n_shared_links']
                                best_path =  evaluation['path']
                        # Add reservation
                        self.add_reservation(best_path, src, dst, rate, n_splits, tos, flow_id, subflow_id)
                # If av_paths is empty
                else:
                    # Break loop
                    break

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
