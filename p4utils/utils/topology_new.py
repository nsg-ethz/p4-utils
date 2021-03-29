import networkx as nx
from ipaddress import ip_interface

class InvalidHostIP(Exception):

    def __init__(self, ip):
        self.message = "".format(ip)
        super(InvalidHostIP, self).__init__('InvalidHostIP: {}'.format(self.message))

    def __str__(self):
        return self.message

class NodeDoesNotExist(Exception):

    def __init__(self, node):
        self.message = 'Node <{}> does not exist'.format(node)
        super().__init__('NodeDoesNotExist: {}'.format(self.message))

    def __str__(self):
        return self.message

class IntfDoesNotExist(Exception):

    def __init__(self, intf, node):
        self.message = 'Interface <{}> does not exist on node <{}>'.format(intf, node)
        super().__init__('IntfDoesNotExist: {}'.format(self.message))

    def __str__(self):
        return self.message

class NetworkGraph(nx.Graph):
    """
    An extension to networkx.classes.Graph which allows querying
    network information and loads the topology from the JSON file
    generated during the execution of p4run. The basic methods
    used to manage nodes are available on the NetworkX documentation
    webpage (https://networkx.org/documentation/stable/index.html) 
    since this class inherits from it.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the Graph."""
        super().__init__(*args, **kwargs)
        self.edge_to_intf = {}          # Stores interface1 dict indexed by [node1][node2]
        self.node_to_intf = {}          # Stores interface1 dict indexed by [node][intfName]
        self.ip_to_host = {}            # Stores host dict indexed by [ip]
        self._populate_dicts()

    def _populate_dicts(self):
        """
        Populate dicts self.intf_to_edge, self.edge_to_intfs and self.node_to_edges
        to speedup searches. This is done by using Graph's properties and methods
        (see https://github.com/networkx/networkx/blob/main/networkx/classes/graph.py).
        """
        for node in self.nodes:
            self.edge_to_intf[node] = {}
            self.node_to_intf[node] = {}

        for node in self.nodes:
            if self.isHost(node):
                ip = self.nodes[node].get('ip', None)
                if ip is not None:
                    self.ip_to_host[ip.split("/")[0]] = {'name': node}
                    self.ip_to_host[ip.split("/")[0]].update(self.nodes[node])

            for neighbor in self.neighbors(node):
                self.edge_to_intf[node][neighbor] = self._edge_to_intf(node, neighbor)
                self.edge_to_intf[neighbor][node] = self._edge_to_intf(neighbor, node)
                self.node_to_intf[node][self.edge_to_intf[node][neighbor]['intfName']] = self.edge_to_intf[node][neighbor]
                self.node_to_intf[neighbor][self.edge_to_intf[neighbor][node]['intfName']] = self.edge_to_intf[neighbor][node]

    def _edge_to_intf(self, node1, node2):
        """
        Returns interface information of node1 facing node2.
        """
        link = self.edges[(node1, node2)]
        intf = {}
        # Get information about node1
        if node1 == link['node1'] and node2 == link['node2']:
            for key, value in link.items():
                if '2' not in key:
                    intf[key.replace('1','')] = value
                else:
                    intf[key.replace('2','_neigh')] = value

        # Get information about node2
        else:
            for key, value in link.items():
                if '1' not in key:
                    intf[key.replace('2','')] = value
                else:
                    intf[key.replace('1','_neigh')] = value
        return intf

    def get_intfs(self, fields=[]):
        """
        Alias of self.edge_to_intf useful for rapid access.
        A dict of dicts which stores the interface of 'node1' which faces 'node2'.
        If fields (list of strings) is specified, the method returns a dict (node1) of dicts (node2)
        of tuples (one per interface) containing all the specified fields' values in 
        the given order (or the single value if only one field is specified).
        """
        if len(fields) > 0:
            reduced_intfs = {}
            for node_a in self.edge_to_intf:
                reduced_intfs[node_a] = {}
                for node_b in self.edge_to_intf[node_a]:
                    reduced_intfs[node_a][node_b] = []
                    for field in fields:
                        reduced_intfs[node_a][node_b].append(self.edge_to_intf[node_a][node_b].get(field, None))
                    reduced_intfs[node_a][node_b] = tuple(reduced_intfs[node_a][node_b])
                    if len(fields) == 1:
                        reduced_intfs[node_a][node_b] = reduced_intfs[node_a][node_b][0]
            return reduced_intfs
        else:
            return self.edge_to_intf

    def get_node_intfs(self, fields=[]):
        """
        Alias of self.node_to_intf useful for rapid access.
        A dict of dicts which stores the interface of 'node' which has the name 'intf'.
        If fields (list of strings) is specified, the method returns a dict (nodes) of dicts (interfaces)
        of tuples (one per interface) containing all the specified fields' values in 
        the given order (or the single value if only one field is specified).
        """
        if len(fields) > 0:
            reduced_intfs = {}
            for node in self.node_to_intf:
                reduced_intfs[node] = {}
                for intf in self.node_to_intf[node]:
                    reduced_intfs[node][intf] = []
                    for field in fields:
                        reduced_intfs[node][intf].append(self.node_to_intf[node][intf].get(field, None))
                    reduced_intfs[node][intf] = tuple(reduced_intfs[node][intf])
                    if len(fields) == 1:
                        reduced_intfs[node][intf] = reduced_intfs[node][intf][0]
            return reduced_intfs
        else:
            return self.node_to_intf

    def get_nodes(self, fields=[]):
        """
        A dict containing all the nodes.
        If fields (list of strings) is specified, the method returns a dict (nodes)
        of tuples (one per node) containing all the specified fields' values in 
        the given order (or the single value if only one field is specified).
        """
        nodes = dict(self.nodes)
        if len(fields) > 0:
            reduced_nodes = {}
            for node in nodes:
                reduced_nodes[node] = []
                for field in fields:
                    reduced_nodes[node].append(nodes[node].get(field, None))
                reduced_nodes[node] = tuple(reduced_nodes[node])
                if len(fields) == 1:
                    reduced_nodes[node] = reduced_nodes[node][0]
            return reduced_nodes
        else:
            return nodes

    def get_switches(self, fields=[]):
        """
        A dict containing all the switches.
        If fields (list of strings) is specified, the method returns a dict (switches)
        of tuples (one per switch) containing all the specified fields' values in 
        the given order (or the single value if only one field is specified).
        """
        switches_subgraph = nx.subgraph_view(self, filter_node=self.isSwitch)
        switches = dict(switches_subgraph.nodes)
        if len(fields) > 0:
            reduced_switches = {}
            for switch in switches:
                reduced_switches[switch] = []
                for field in fields:
                    reduced_switches[switch].append(switches[switch].get(field, None))
                reduced_switches[switch] = tuple(reduced_switches[switch])
                if len(fields) == 1:
                    reduced_switches[switch] = reduced_switches[switch][0]
            return reduced_switches
        else:
            return switches

    def get_p4switches(self, fields=[]):
        """
        A dict containing all the P4 switches.
        If fields (list of strings) is specified, the method returns a dict (p4switches)
        of tuples (one per P4 switch) containing all the specified fields' values in 
        the given order (or the single value if only one field is specified).
        """
        p4switches_subgraph = nx.subgraph_view(self, filter_node=self.isP4Switch)
        p4switches = dict(p4switches_subgraph.nodes)
        if len(fields) > 0:
            reduced_p4switches = {}
            for p4switch in p4switches:
                reduced_p4switches[p4switch] = []
                for field in fields:
                    reduced_p4switches[p4switch].append(p4switches[p4switch].get(field, None))
                reduced_p4switches[p4switch] = tuple(reduced_p4switches[p4switch])
                if len(fields) == 1:
                    reduced_p4switches[p4switch] = reduced_p4switches[p4switch][0]
            return reduced_p4switches
        else:
            return p4switches

    def get_p4rtswitches(self, fields=[]):
        """
        A dict containing all the P4 runtime switches.
        If fields (list of strings) is specified, the method returns a dict (p4rtswitches)
        of tuples (one per P4 runtime switch) containing all the specified fields' values in 
        the given order (or the single value if only one field is specified).
        """
        p4rtswitches_subgraph = nx.subgraph_view(self, filter_node=self.isP4RuntimeSwitch)
        p4rtswitches = dict(p4rtswitches_subgraph.nodes)
        if len(fields) > 0:
            reduced_p4rtswitches = {}
            for p4rtswitch in p4rtswitches:
                reduced_p4rtswitches[p4rtswitch] = []
                for field in fields:
                    reduced_p4rtswitches[p4rtswitch].append(p4rtswitches[p4rtswitch].get(field, None))
                reduced_p4rtswitches[p4rtswitch] = tuple(reduced_p4rtswitches[p4rtswitch])
                if len(fields) == 1:
                    reduced_p4rtswitches[p4rtswitch] = reduced_p4rtswitches[p4rtswitch][0]
            return reduced_p4rtswitches
        else:
            return p4rtswitches

    def get_hosts(self, fields=[]):
        """
        A dict containing all the hosts.
        If fields (list of strings) is specified, the method returns a dict (hosts)
        of tuples (one per hosts) containing all the specified fields' values in 
        the given order (or the single value if only one field is specified).
        """
        hosts_subgraph = nx.subgraph_view(self, filter_node=self.isHost)
        hosts = dict(hosts_subgraph.nodes)
        if len(fields) > 0:
            reduced_hosts = {}
            for host in hosts:
                reduced_hosts[host] = []
                for field in fields:
                    reduced_hosts[host].append(hosts[host].get(field, None))
                reduced_hosts[host] = tuple(reduced_hosts[host])
                if len(fields) == 1:
                    reduced_hosts[host] = reduced_hosts[host][0]
            return reduced_hosts
        else:
            return hosts

    def get_routers(self, fields=[]):
        """
        A dict containing all the routers.
        If fields (list of strings) is specified, the method returns a dict (routers)
        of tuples (one per router) containing all the specified fields' values in 
        the given order (or the single value if only one field is specified).
        """
        routers_subgraph = nx.subgraph_view(self, filter_node=self.isRouter)
        routers = dict(routers_subgraph.nodes)
        if len(fields) > 0:
            reduced_routers = {}
            for router in routers:
                reduced_routers[router] = []
                for field in fields:
                    reduced_routers[router].append(routers[router].get(field, None))
                reduced_routers[router] = tuple(reduced_routers[router])
                if len(fields) == 1:
                    reduced_routers[router] = reduced_routers[router][0]
            return reduced_routers
        else:
            return routers

    def get_neighbors(self, n):
        """
        A list containing all the names of the neighbors of node n.
        """
        return list(self.get_intfs()[n].keys())

    def isNode(self, node):
        """Return True if the node exists."""
        return node in self.get_nodes()

    def checkNode(self, node):
        """Check if node exists, else raise a NodeDoesNotExist error."""
        if not self.isNode(node):
            raise NodeDoesNotExist(node)

    def isIntf(self, node1, node2):
        """Return True if the intf exists by specifying its edge."""
        if node1 not in self.edge_to_intf:
            return False
        if node2 not in self.edge_to_intf[node1]:
            return False
        return True

    def checkIntf(self, node1, node2):
        """Check if interface exists, else raise a IntfDoesNotExist error."""
        if not self.isIntf(node1, node2):
            raise NodeDoesNotExist(node)

    def isHost(self, node):
        """Return True if the node is a host."""
        self.checkNode(node)
        return self.get_nodes()[node].get('isHost', False)

    def isSwitch(self, node):
        """Return True if the node is a switch."""
        self.checkNode(node)
        return self.get_nodes()[node].get('isSwitch', False)

    def isP4Switch(self, node):
        """Return True if the node is a P4 switch."""
        self.checkNode(node)
        return self.get_nodes()[node].get('isP4Switch', False)

    def isP4RuntimeSwitch(self, node):
        """Return True if the node is a P4 runtime switch."""
        self.checkNode(node)
        return self.get_nodes()[node].get('isP4RuntimeSwitch', False)

    def isRouter(self, node):
        """Return True if the node is a router."""
        self.checkNode(node)
        return self.get_nodes()[node].get('isRouter', False)

    def isType(self, node, node_type):
        """
        Check custom node type. Possible values are:
            host
            switch
            p4switch
            p4runtimeswitch
            router
        """
        if node_type == 'host':
            return self.isHost(node)
        elif node_type == 'switch':
            return self.isSwitch(node)
        elif node_type == 'p4switch':
            return self.isP4Switch(node)
        elif node_type == 'p4runtimeswitch':
            return self.isP4RuntimeSwitch(node)
        elif node_type == 'router':
            return self.isRouter(node)
        else:
            print('Unknown node type {}.'.format(node_type))

    def _node_interface(self, node, intf):
        """Returns interface information of node1's interface intf."""
        try:
            intfs = self.node_to_intf[node]
        except KeyError:
            raise NodeDoesNotExist(node)
        try:
            return intfs[intf]
        except KeyError:
            raise IntfDoesNotExist(intf, node)

    def node_to_node_interface_ip(self, node1, node2):
        """Return the ip_interface for node1 facing node2."""
        self.checkIntf(node1, node2)
        return self.get_intfs()[node1][node2].get('ip', None)

    def node_to_node_interface_bw(self, node1, node2):
        """
        Return the bandwidth capacity of the interface on node1 facing node2.
        If it is unlimited, return -1.
        """
        self.checkIntf(node1, node2)
        if self.get_intfs()[node1][node2].get('bw', None) is None:
            return -1
        else:
            return self.get_intfs()[node1][node2]['bw']
    
    def node_interface_ip(self, node, intf):
        """Returns the IP address of a given interface and node."""
        ip = self._node_interface(node, intf).get('ip', None)
        if ip is not None:
            return ip.split("/")[0]
        else:
            return None

    def node_interface_bw(self, node, intf):
        """Returns the bw of a given interface and node."""
        if self._node_interface(node, intf).get('bw', None) is None:
            return -1
        else:
            return self._node_interface(node, intf)['bw']

    def subnet(self, node1, node2):
        """Return the subnet linking node1 and node2 (from the point of view of node1)."""
        ip = self.node_to_node_interface_ip(node1, node2)
        if ip is not None:
            return ip_interface(ip).network.with_prefixlen
        else:
            return None

    def get_interfaces(self, node):
        """Returns node's interfaces names."""
        self.checkNode(node)
        return list(self.node_to_intf[node].keys())

    def get_cpu_port_intf(self, p4switch, quiet=False):
        """
        Returns the P4 switch's CPU interface

        Args:
            p4switch: name of the P4 switch

        Returns:
            CPU interface of the P4 switch
        """
        if self.isP4Switch(p4switch) and self.get_nodes()[p4switch]['cpu_port']:
            return [x for x in self.node_to_intf[p4switch].keys() if 'cpu' in x][0]
        else:
            if not quiet:
                print('Switch {} has no cpu port.'.format(p4switch))
            return None

    def get_cpu_port_index(self, p4switch, quiet=False):
        """
        Returns the port number of P4 switch's CPU port

        Args:
            p4switch: name of the P4 switch

        Returns:
            Port number of the P4 switch
        """
        if self.isP4Switch(p4switch) and self.get_nodes()[p4switch]['cpu_port']:
            intf = self.get_cpu_port_intf(p4switch)
            return self._node_interface(p4switch, intf)['port']
        else:
            if not quiet:
                print('Switch {} has no cpu port.'.format(p4switch))
            return None

    def get_thrift_port(self, p4switch):
        """Return the Thrift port used to communicate with the P4 switch."""
        if self.isP4Switch(p4switch):
            return self.get_nodes()[p4switch]['thrift_port']
        else:
            raise TypeError('{} is not a P4 switch.'.format(p4switch))

    def get_thrift_ip(self, p4switch):
        """Return the Thrift ip used to communicate with the P4 switch."""
        if self.isP4Switch(p4switch):
            print('This method is not yet fully implemented, all switches listen on 0.0.0.0.')
            return '0.0.0.0'
            #return self.get_nodes()[switch]['thrift_ip']
        else:
            raise TypeError('{} is not a P4 switch.'.format(p4switch))

    def get_grpc_port(self, p4rtswitch):
        """Return the grpc port used to communicate with the P4 runtime switch."""
        if self.isP4RuntimeSwitch(p4rtswitch):
            return self.get_nodes()[p4rtswitch]['grpc_port']
        else:
            raise TypeError('{} is not a P4 runtime switch.'.format(p4rtswitch))

    def get_grpc_ip(self, p4rtswitch):
        """Return the grpc ip used to communicate with the P4 runtime switch."""
        if self.isP4RuntimeSwitch(p4rtswitch):
            print('This method is not yet fully implemented, all switches listen on 0.0.0.0.')
            return '0.0.0.0'
            #return self.get_nodes()[p4rtswitch]['thrift_ip']
        else:
            raise TypeError('{} is not a P4 switch.'.format(p4rtswitch))

    def get_ctl_cpu_intf(self, p4switch):
        """Returns the controller side cpu interface used to listen for cpu packets."""
        if self.isP4Switch(p4switch) and self.get_nodes()[p4switch]['cpu_port']:
            return self.get_intfs()['sw-cpu'][p4switch]['intfName']
        else:
            raise TypeError('Switch {} has no cpu port.'.format(p4switch))

    def get_host_name(self, ip):
        """
        Returns the host name to an IP address.

        Args:
            ip: host's ip w/o subnet

        Returns:
            name of the host whose ip corresponds to the one provided
        """
        host = self.ip_to_host.get(ip, None)
        if host:
            return host['name']
        else:
            raise InvalidHostIP(ip)
        
    def get_host_first_interface(self, host):
        """Returns the first interface from a host. Assume it's single-homed.

        Args:
            host: host name

        Returns:
            interface name (str)
        """
        if self.isHost(host):
            return list(self.node_to_intf[host].keys())[0]
        else:
            raise TypeError('{} is not a host.'.format(host))

    def get_host_gateway_name(self, host):
        """Get host gateway name."""
        if self.isHost(host):
            return self._node_interface(host, self.get_host_first_interface(host))['node_neigh']
        else:
            raise TypeError('{} is not a host.'.format(host))
        
    def get_host_ip(self, host):
        """Returns the IP to a host name.

        Args:
            name: host's name
        """
        if self.isHost(host):
            ip = self.get_nodes()[host].get('ip', None)
            if ip is not None:
                return ip.split("/")[0]
            else:
                return None
        else:
            raise TypeError('{} is not a host.'.format(host))

    def get_host_mac(self, host):
        """
        Returns the mac to a host name.

        Args:
            name: host's name
        """
        self.checkNode(host)
        intf = self.get_host_first_interface(host)
        return self._node_interface(host, intf)['addr']

    def get_p4switch_id(self, p4switch):
        """
        Returns the ID of a P4 switch.

        Args:
            p4switch: P4 switch name in the topology

        Raises:
            TypeError if sw_name is not a P4 switch

        Returns:
            ID of P4 switch as a string
        """
        if self.isP4Switch(p4switch):
            return self.get_nodes()[p4switch]['device_id']
        else:
            raise TypeError('{} is not a P4 switch.'.format(p4switch))

    def are_neighbors(self, node1, node2):
        """
        Returns if two nodes are direct neighbors.

        Args:
            node1: first node
            node2: second node

        Returns:
            True if node1 and node2 are neighbors
        """
        self.checkNode(node1)
        self.checkNode(node2)
        return node1 in self.get_neighbors(node2)
        
    def get_hosts_connected_to(self, node):
        """
        Returns the hosts directly connected to the node.

        Args:
            node:

        Returns: list of hosts
        """
        self.checkNode(node)
        nodes = self.get_neighbors(node)
        return [host for host in nodes if self.isHost(host)]

    def get_switches_connected_to(self, node):
        """
        Returns the switches directly connected to the node.

        Args:
            node:

        Returns: list of switches
        """
        self.checkNode(node)
        nodes = self.get_neighbors(node)
        return [switch for switch in nodes if self.isSwitch(switch)]

    def get_p4switches_connected_to(self, node):
        """
        Returns the P4 switches directly connected to the node.

        Args:
            node:

        Returns: list of switches
        """
        self.checkNode(node)
        nodes = self.get_neighbors(node)
        return [switch for switch in nodes if self.isP4Switch(switch)]

    def get_routers_connected_to(self, node):
        """
        Returns the routers directly connected to the node.

        Args:
            node:

        Returns: list of routers
        """
        self.checkNode(node)
        nodes = self.get_neighbors(node)
        return [router for router in nodes if self.isRouter(router)]

    def get_direct_host_networks_from_switch(self, switch):
        """
        Returns all the subnetworks a switch can reach directly.

        Args:
            switch: switch name

        Returns: Returns set of networks
        """
        self.checkNode(switch)
        networks = []
        hosts = self.get_hosts_connected_to(switch)
        for host in hosts:
            networks += [self.subnet(host, switch)]
        return set(networks)

    def get_interfaces_to_node(self, node):
        """
        Returns dictionary with all interface_name -> neighbor node.

        Args:
            node: node's name
        """
        self.checkNode(node)
        intfs = {}
        for intf, params in self.node_to_intf[node].items():
            intfs[intf] = params['node_neigh']
        return intfs
    
    def interface_to_node(self, node, intf):
        """
        Returns name of the neigbor at interface 'intf' of node 'node'.

        Args:
            node: node we are quering
            intf: name of the interface
        """
        return self._node_interface(node, intf)['node_neigh']

    def interface_to_port(self, node, intf):
        """
        Returns port number of the interface 'intf' of node 'node'.

        Args:
            node: node we are quering
            intf: name of the interface
        """
        return self._node_interface(node, intf)['port']

    def node_to_node_port_num(self, node1, node2):
        """
        Returns the port number from node1 point of view that connects to node2.

        Args:
            node1: src node
            node2: dst node
        """
        self.checkIntf(node1, node2)
        return self.get_intfs()[node1][node2].get('port', None)

    def node_to_node_mac(self, node1, node2):
        """
        Returns mac address of node1's interface facing node2.

        Args:
            node1: src node
            node2: dst node
        """
        self.checkIntf(node1, node2)
        return self.get_intfs()[node1][node2].get('addr', None)

    def total_number_of_paths(self):
        """Returns the total number of shortests paths between all host pairs in the network."""
        total_paths = 0
        for host in self.get_hosts():
            for host_pair in self.get_hosts():
                if host == host_pair:
                    continue
                # compute the number of paths
                npaths = sum(1 for _ in nx.all_shortest_paths(self, host, host_pair, 'weight'))
                total_paths += npaths
        return total_paths

    def get_shortest_paths_between_nodes(self, node1, node2):
        """
        Returns all the shortest paths between node1 and node2.

        Args:
            node1: src node
            node2: dst node

        Returns: List of shortests paths
        """
        self.checkNode(node1)
        self.checkNode(node2)
        paths = nx.all_shortest_paths(self, node1, node2, 'weight')
        paths = [tuple(x) for x in paths]
        return paths

    def get_all_paths_between_nodes(self, node1, node2):
        """
        Returns all the simple (i.e. with no repeated nodes) paths 
        between node1 and node2.
        
        Args:
            node1: src node
            node2: dst node

        Returns: List of shortests paths
        """
        self.checkNode(node1)
        self.checkNode(node2)
        paths = nx.shortest_simple_paths(self, node1, node2, 'weight')
        paths = [tuple(x) for x in paths]
        return paths

    def keep_only_switches(self):
        """Returns a networkx subgraph including only switch nodes."""
        return self.subgraph(list(self.get_switches().keys()))

    def keep_only_p4switches(self):
        """Returns a networkx subgraph including only P4 switch nodes."""
        return self.subgraph(list(self.get_p4switches().keys()))

    def keep_only_p4switches_and_hosts(self):
        """Returns a networkx subgraph including only hosts and P4 switch nodes."""
        return self.subgraph(list(self.get_p4switches().keys()) + list(self.get_hosts().keys()))

    # Drawing
    def set_node_shape(self, node, shape):
        """Sets node's shape. Used when plotting the network."""
        self.get_nodes()[node]['node_shape'] = shape

    def set_node_color(self, node, color):
        """Sets node's color. Used when plotting the network."""
        self.get_nodes()[node]['node_color'] = color

    def set_node_type_shape(self, node_type, shape):
        """
        Sets the shape of the nodes filtered by type.

        Possible node types:
            host
            switch
            p4switch
            p4runtimeswitch
            router

        Used when plotting the network.
        """
        for node in self.get_nodes():
            if self.isType(self.get_nodes()[node], node_type):
                self.set_node_shape(node, shape)

    def set_node_type_color(self, node_type, color):
        """
        Sets the color of the nodes filtered by type.

        Possible node types:
            host
            switch
            p4switch
            p4runtimeswitch
            router

        Used when plotting the network.
        """
        for node in self.get_nodes():
            if self.isType(self.get_nodes()[node], node_type):
                self.set_node_color(node, color)
